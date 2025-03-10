/**
 * @license
 * Copyright 2018-2021 Streamlit Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

describe("st.balloons", () => {
  before(() => {
    cy.visit("http://localhost:3000/");
  });

  it("uses negative bottom margin styling", () => {
    // balloons use negative bottom margin to prevent the flexbox gap (instead of display: none like st.empty)
    cy.get(".balloons")
      .eq(0)
      .parent()
      .should("have.css", "margin-bottom");

    cy.get(".balloons")
      .eq(0)
      .parent()
      .should("not.have.css", "display", "none");
  });
});
