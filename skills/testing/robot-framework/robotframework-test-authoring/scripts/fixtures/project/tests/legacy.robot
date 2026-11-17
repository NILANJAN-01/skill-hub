*** Settings ***
Library         Browser
Library         Telnet
Force Tags      legacy

*** Variables ***
${ADMIN_PASSWORD}       hunter22
${TOKEN: Secret}        abc123
${API_TOKEN: Secret}    %{API_TOKEN}

*** Test Cases ***
Old Style Test
    :FOR    ${i}    IN RANGE    3
    \    Log    ${i}
    Run Keyword If    ${TRUE}    Log    yes
    Set Suite Variable    ${X}    1
    Sleep    3s
    ${out}=    Run    ls
    VAR    ${shared}    scope=SUITE
    Exit For Loop If    ${TRUE}

New Style Test
    [Metadata]    Issue    QA-1
    VAR    ${count: int}    3
    GROUP    Login
        Log    hello
    END

*** Keywords ***
Old Keyword
    [Return]    ${1}

Documented Keyword
    [Documentation]    Does a thing.
    [Setup]    Log    setup
    RETURN    ${2}
