package com.example.billing;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import java.util.Arrays;
import java.util.Collection;

import org.junit.Before;
import org.junit.Ignore;
import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.ExpectedException;
import org.junit.rules.TemporaryFolder;
import org.junit.runner.RunWith;
import org.junit.runners.Parameterized;

@RunWith(Parameterized.class)
public class InvoiceTest {

    @Rule
    public TemporaryFolder folder = new TemporaryFolder();

    @Rule
    public ExpectedException thrown = ExpectedException.none();

    @Parameterized.Parameters
    public static Collection<Object[]> data() {
        return Arrays.asList(new Object[][] {{1, 10}, {2, 20}});
    }

    private final int quantity;
    private final int expected;
    private Invoice invoice;

    public InvoiceTest(int quantity, int expected) {
        this.quantity = quantity;
        this.expected = expected;
    }

    @Before
    public void setUp() {
        invoice = new Invoice();
    }

    @Test
    public void total() {
        assertEquals("total for quantity", expected, invoice.total(quantity));
    }

    @Test(expected = IllegalArgumentException.class)
    public void negativeQuantity() {
        invoice.total(-1);
    }

    @Test(timeout = 1000)
    public void fast() throws Exception {
        Thread.sleep(10);
        assertTrue(invoice.total(1) > 0);
    }

    @Ignore
    @Test
    public void pending() {
        invoice.total(3);
    }
}
