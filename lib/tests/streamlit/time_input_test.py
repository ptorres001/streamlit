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

"""time_input unit test."""

from tests import testutil
import streamlit as st
from parameterized import parameterized
from datetime import datetime
from datetime import time


class TimeInputTest(testutil.DeltaGeneratorTestCase):
    """Test ability to marshall time_input protos."""

    def test_just_label(self):
        """Test that it can be called with no value."""
        st.time_input("the label")

        c = self.get_delta_from_queue().new_element.time_input
        self.assertEqual(c.label, "the label")
        self.assertLessEqual(
            datetime.strptime(c.default, "%H:%M").time(), datetime.now().time()
        )
        self.assertEqual(c.disabled, False)

    def test_just_disabled(self):
        """Test that it can be called with disabled param."""
        st.time_input("the label", disabled=True)

        c = self.get_delta_from_queue().new_element.time_input
        self.assertEqual(c.disabled, True)

    @parameterized.expand(
        [(time(8, 45), "08:45"), (datetime(2019, 7, 6, 21, 15), "21:15")]
    )
    def test_value_types(self, arg_value, proto_value):
        """Test that it supports different types of values."""
        st.time_input("the label", arg_value)

        c = self.get_delta_from_queue().new_element.time_input
        self.assertEqual(c.label, "the label")
        self.assertEqual(c.default, proto_value)

    def test_inside_column(self):
        """Test that it works correctly inside of a column."""
        col1, col2 = st.columns([3, 2])

        with col1:
            st.time_input("foo")

        all_deltas = self.get_all_deltas_from_queue()

        # 4 elements will be created: 1 horizontal block, 2 columns, 1 widget
        self.assertEqual(len(all_deltas), 4)
        time_input_proto = self.get_delta_from_queue().new_element.time_input

        self.assertEqual(time_input_proto.label, "foo")
