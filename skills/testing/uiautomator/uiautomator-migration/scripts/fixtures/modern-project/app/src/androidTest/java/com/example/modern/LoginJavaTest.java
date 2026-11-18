package com.example.modern;

import static org.junit.Assert.assertNotNull;

import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.uiautomator.By;
import androidx.test.uiautomator.BySelector;
import androidx.test.uiautomator.UiDevice;
import androidx.test.uiautomator.UiObject2;
import androidx.test.uiautomator.Until;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class LoginJavaTest {
    private static final long TIMEOUT_MS = 10_000;
    private UiDevice device;

    @Before
    public void setUp() {
        device = UiDevice.getInstance(InstrumentationRegistry.getInstrumentation());
    }

    @Test
    public void signIn() {
        BySelector signIn = By.res("sign_in_button");
        UiObject2 button = device.wait(Until.findObject(signIn), TIMEOUT_MS);
        assertNotNull("sign in button", button);
        button.clickAndWait(Until.newWindow(), TIMEOUT_MS);
    }
}
