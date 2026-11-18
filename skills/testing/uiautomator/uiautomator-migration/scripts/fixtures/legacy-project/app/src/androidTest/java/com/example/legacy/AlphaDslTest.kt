package com.example.legacy

import android.content.Intent
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.uiautomator.PermissionDialog
import androidx.test.uiautomator.uiAutomator
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class AlphaDslTest {
    @Test
    fun alphaApis() = uiAutomator {
        startApp("com.example.legacy")
        onView { viewIdResourceName == "sign_in" }.click()
        onElement { text == "Continue" }.click()
        clearAppData("com.example.legacy")
        startIntent(Intent(Intent.ACTION_VIEW))
    }

    @Test
    fun lowercase() = uiautomator {
        onElement { contentDescription == "Menu" }.click()
    }
}
