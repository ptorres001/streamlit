# Copyright 2018-2021 Streamlit Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""st.memo unit tests."""
import pickle
import re
import unittest
from unittest.mock import patch, mock_open, MagicMock, Mock

import streamlit as st
from streamlit import StreamlitAPIException, file_util
from streamlit.caching import memo_decorator, clear_memo_cache
from streamlit.caching.cache_errors import CacheError
from streamlit.caching.memo_decorator import get_cache_path, get_memo_stats_provider
from streamlit.stats import CacheStat


class MemoTest(unittest.TestCase):
    def tearDown(self):
        # Some of these tests reach directly into _cache_info and twiddle it.
        # Reset default values on teardown.
        memo_decorator.MEMO_CALL_STACK._cached_func_stack = []
        memo_decorator.MEMO_CALL_STACK._suppress_st_function_warning = 0
        clear_memo_cache()

    @patch.object(st, "exception")
    def test_mutate_return(self, exception):
        """Mutating a memoized return value is legal, and *won't* affect
        future accessors of the data."""

        @st.experimental_memo
        def f():
            return [0, 1]

        r1 = f()

        r1[0] = 1

        r2 = f()

        exception.assert_not_called()

        self.assertEqual(r1, [1, 1])
        self.assertEqual(r2, [0, 1])

    @patch("streamlit.caching.memo_decorator._TTLCACHE_TIMER")
    def test_ttl(self, timer_patch):
        """Entries should expire after the given ttl."""
        one_day = 60 * 60 * 24

        # Create 2 cached functions to test that they don't interfere
        # with each other.
        foo_vals = []

        @st.experimental_memo(ttl=one_day)
        def foo(x):
            foo_vals.append(x)
            return x

        bar_vals = []

        @st.experimental_memo(ttl=one_day * 2)
        def bar(x):
            bar_vals.append(x)
            return x

        # Store a value at time 0
        timer_patch.return_value = 0
        foo(0)
        bar(0)
        self.assertEqual([0], foo_vals)
        self.assertEqual([0], bar_vals)

        # Advance our timer, but not enough to expire our value.
        timer_patch.return_value = one_day * 0.5
        foo(0)
        bar(0)
        self.assertEqual([0], foo_vals)
        self.assertEqual([0], bar_vals)

        # Advance our timer enough to expire foo, but not bar.
        timer_patch.return_value = one_day * 1.5
        foo(0)
        bar(0)
        self.assertEqual([0, 0], foo_vals)
        self.assertEqual([0], bar_vals)

        # Expire bar. Foo's second value was inserted at time=1.5 days,
        # so it won't expire until time=2.5 days
        timer_patch.return_value = (one_day * 2) + 1
        foo(0)
        bar(0)
        self.assertEqual([0, 0], foo_vals)
        self.assertEqual([0, 0], bar_vals)

        # Expire foo for a second time.
        timer_patch.return_value = (one_day * 2.5) + 1
        foo(0)
        bar(0)
        self.assertEqual([0, 0, 0], foo_vals)
        self.assertEqual([0, 0], bar_vals)


class MemoPersistTest(unittest.TestCase):
    """st.memo disk persistence tests"""

    def tearDown(self) -> None:
        clear_memo_cache()

    @patch("streamlit.caching.memo_decorator.streamlit_write")
    def test_dont_persist_by_default(self, mock_write):
        @st.experimental_memo
        def foo():
            return "data"

        foo()
        mock_write.assert_not_called()

    @patch("streamlit.caching.memo_decorator.streamlit_write")
    def test_persist_path(self, mock_write):
        """Ensure we're writing to ~/.streamlit/cache/*.memo"""

        @st.experimental_memo(persist="disk")
        def foo():
            return "data"

        foo()
        mock_write.assert_called_once()

        write_path = mock_write.call_args[0][0]
        match = re.fullmatch(
            r"/mock/home/folder/.streamlit/cache/.*?\.memo", write_path
        )
        self.assertIsNotNone(match)

    @patch("streamlit.file_util.os.stat", MagicMock())
    @patch(
        "streamlit.file_util.open",
        mock_open(read_data=pickle.dumps("mock_pickled_value")),
    )
    @patch(
        "streamlit.caching.memo_decorator.streamlit_read",
        wraps=file_util.streamlit_read,
    )
    def test_read_persisted_data(self, mock_read):
        """We should read persisted data from disk on cache miss."""

        @st.experimental_memo(persist="disk")
        def foo():
            return "actual_value"

        data = foo()
        mock_read.assert_called_once()
        self.assertEqual("mock_pickled_value", data)

    @patch("streamlit.file_util.os.stat", MagicMock())
    @patch("streamlit.file_util.open", mock_open(read_data="bad_pickled_value"))
    @patch(
        "streamlit.caching.memo_decorator.streamlit_read",
        wraps=file_util.streamlit_read,
    )
    def test_read_bad_persisted_data(self, mock_read):
        """If our persisted data is bad, we raise an exception."""

        @st.experimental_memo(persist="disk")
        def foo():
            return "actual_value"

        with self.assertRaises(CacheError) as error:
            foo()
        mock_read.assert_called_once()
        self.assertEqual("Unable to read from cache", str(error.exception))

    def test_bad_persist_value(self):
        """Throw an error if an invalid value is passed to 'persist'."""
        with self.assertRaises(StreamlitAPIException) as e:

            @st.experimental_memo(persist="yesplz")
            def foo():
                pass

        self.assertEqual(
            "Unsupported persist option 'yesplz'. Valid values are 'disk' or None.",
            str(e.exception),
        )

    @patch("shutil.rmtree")
    def test_clear_all_disk_caches(self, mock_rmtree):
        """`clear_all` should remove the disk cache directory if it exists."""

        # If the cache dir exists, we should delete it.
        with patch("os.path.isdir", MagicMock(return_value=True)):
            clear_memo_cache()
            mock_rmtree.assert_called_once_with(get_cache_path())

        mock_rmtree.reset_mock()

        # If the cache dir does not exist, we shouldn't try to delete it.
        with patch("os.path.isdir", MagicMock(return_value=False)):
            clear_memo_cache()
            mock_rmtree.assert_not_called()

    @patch("streamlit.file_util.os.stat", MagicMock())
    @patch(
        "streamlit.file_util.open",
        wraps=mock_open(read_data=pickle.dumps("mock_pickled_value")),
    )
    @patch("streamlit.caching.memo_decorator.os.remove")
    def test_clear_one_disk_cache(self, mock_os_remove: Mock, mock_open: Mock):
        """A memoized function's clear_cache() property should just clear
        that function's cache."""

        @st.experimental_memo(persist="disk")
        def foo(val):
            return "actual_value"

        foo(0)
        foo(1)

        # We should've opened two files, one for each distinct "foo" call.
        self.assertEqual(2, mock_open.call_count)

        # Get the names of the two files that were created. These will look
        # something like '/mock/home/folder/.streamlit/cache/[long_hash].memo'
        created_filenames = {
            mock_open.call_args_list[0][0][0],
            mock_open.call_args_list[1][0][0],
        }

        mock_os_remove.assert_not_called()

        # Clear foo's cache
        foo.clear()

        # os.remove should have been called once for each of our created cache files
        self.assertEqual(2, mock_os_remove.call_count)

        removed_filenames = {
            mock_os_remove.call_args_list[0][0][0],
            mock_os_remove.call_args_list[1][0][0],
        }

        # The two files we removed should be the same two files we created.
        self.assertEqual(created_filenames, removed_filenames)


class MemoStatsProviderTest(unittest.TestCase):
    def setUp(self):
        # Guard against external tests not properly cache-clearing
        # in their teardowns.
        clear_memo_cache()

    def tearDown(self):
        clear_memo_cache()

    def test_no_stats(self):
        self.assertEqual([], get_memo_stats_provider().get_stats())

    def test_multiple_stats(self):
        @st.experimental_memo
        def foo(count):
            return [3.14] * count

        @st.experimental_memo
        def bar():
            return "shivermetimbers"

        foo(1)
        foo(53)
        bar()
        bar()

        foo_cache_name = f"{foo.__module__}.{foo.__qualname__}"
        bar_cache_name = f"{bar.__module__}.{bar.__qualname__}"

        expected = [
            CacheStat(
                category_name="st_memo",
                cache_name=foo_cache_name,
                byte_length=get_byte_length([3.14]),
            ),
            CacheStat(
                category_name="st_memo",
                cache_name=foo_cache_name,
                byte_length=get_byte_length([3.14] * 53),
            ),
            CacheStat(
                category_name="st_memo",
                cache_name=bar_cache_name,
                byte_length=get_byte_length("shivermetimbers"),
            ),
        ]

        # The order of these is non-deterministic, so check Set equality
        # instead of List equality
        self.assertEqual(set(expected), set(get_memo_stats_provider().get_stats()))


def get_byte_length(value):
    """Return the byte length of the pickled value."""
    return len(pickle.dumps(value))
