package com.example.orders;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.fail;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.MethodOrderer;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestMethodOrder;
import org.junit.jupiter.api.condition.EnabledForJreRange;
import org.junit.jupiter.api.condition.JRE;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

@TestMethodOrder(MethodOrderer.Alphanumeric.class)
class OrderServiceTest {

    static OrderService service;

    @BeforeAll
    void startService() {
        service = new OrderService();
    }

    @Test
    private void privateTestNeverRuns() {
        assertTrue(service.isReady());
    }

    @Test
    int returnsAValue() {
        return service.count();
    }

    @Test
    void placesOrder() {
        service.place("book");
    }

    @Test
    void messageFirst() {
        assertEquals("count after place", 1, service.count());
    }

    @Test
    void tryFailCatch() {
        try {
            service.place(null);
            fail("expected an exception");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("item"));
        }
    }

    @Disabled
    @Test
    void flaky() {
        assertTrue(service.equals(service));
    }

    @ParameterizedTest
    @CsvSource({
        "book, 1",
        "pen, 2"
    })
    void parameterized(String item, int expected) {
        assertEquals(expected, service.priceOf(item));
    }

    @EnabledForJreRange(min = JRE.JAVA_11)
    @Test
    void onNewJava() {
        assertEquals(0, service.count());
    }

    @Nested
    static class WhenEmpty {
        @Test
        void hasNoOrders() {
            assertEquals(0, service.count());
        }
    }
}
