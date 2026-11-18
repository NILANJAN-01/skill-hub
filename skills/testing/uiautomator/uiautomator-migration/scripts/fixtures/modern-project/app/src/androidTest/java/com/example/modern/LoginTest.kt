package com.example.modern

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.Direction
import androidx.test.uiautomator.onElement
import androidx.test.uiautomator.scrollToElement
import androidx.test.uiautomator.simpleViewResourceName
import androidx.test.uiautomator.textAsString
import androidx.test.uiautomator.uiAutomator
import androidx.test.uiautomator.watcher.PermissionDialog
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class LoginTest {
    @Test
    fun signIn() = uiAutomator {
        startApp(APP)
        watchFor(PermissionDialog) { clickAllow() }
        onElement { viewIdResourceName == "login_form" }
            .onElement { simpleViewResourceName() == "email" }
            .setText("user@example.com")
        onElement { textAsString() == "Sign in" }.click()
        onElement { isScrollable }.scrollToElement(Direction.DOWN) { textAsString() == "Settings" }.click()
        activeWindow().waitForStable()
    }

    companion object {
        private const val APP = "com.example.modern"
    }
}
