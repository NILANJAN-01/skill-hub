*** Settings ***
Documentation       Fixture suite used to produce real output files for the tests.
Test Tags           checkout

*** Variables ***
${TOKEN: Secret}        %{FIXTURE_TOKEN=dev-token}
${RETRIES: int}         3
@{NUMS: int}            1    2    3
${FLAKY_PASS}           ${FALSE}

*** Test Cases ***
Modern Syntax Works
    [Tags]    smoke
    [Metadata]    Issue    QA-7
    VAR    ${total: int}    0
    GROUP    Sum numbers
        FOR    ${i}    ${n}    IN ENUMERATE    @{NUMS}    start=1
            ${total}=    Evaluate    ${total} + ${n}
        END
    END
    Should Be Equal    ${total}    ${6}
    VAR    ${count: int}    ${RETRIES}
    WHILE    ${count} > 0    limit=10
        ${count}=    Evaluate    ${count} - 1
        IF    ${count} == 1    BREAK
    END
    TRY
        Fail    expected problem
    EXCEPT    expected*    type=GLOB
        Log    handled
    END
    FOR    ${a}    ${b}    IN ZIP    ${{[1, 2]}}    ${{[3, 4]}}    mode=STRICT
        Log    ${a} ${b}
    END
    Use Secret    ${TOKEN}

Price Should Match
    [Tags]    regression
    Check Total    10    12

Missing Keyword
    This Keyword Does Not Exist

Slow Step
    [Timeout]    0.2s
    Sleep    1s

Skipped On Purpose
    Skip    Feature flag is off

Flaky Payment
    Should Be True    ${FLAKY_PASS}    Payment gateway did not answer

*** Keywords ***
Check Total
    [Arguments]    ${expected: int}    ${actual: int}
    [Setup]    Log    checking
    Should Be Equal    ${actual}    ${expected}    Total differs

Use Secret
    [Arguments]    ${token: Secret}
    Log    ${token}
