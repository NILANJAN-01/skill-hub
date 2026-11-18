package com.example.shop;

import static org.junit.jupiter.api.Assertions.assertAll;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.nio.file.Files;
import java.nio.file.Path;

import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;
import org.junit.jupiter.params.provider.ValueSource;

@DisplayName("PriceCalculator")
class PriceCalculatorTest {

    static Catalog catalog;
    PriceCalculator calculator;

    @BeforeAll
    static void loadCatalog() {
        catalog = Catalog.sample();
    }

    @BeforeEach
    void setUp() {
        calculator = new PriceCalculator(catalog);
    }

    @Test
    @DisplayName("adds VAT to the net price")
    void addsVat() {
        assertEquals(120, calculator.gross(100));
    }

    @ParameterizedTest(name = "{0} items cost {1}")
    @CsvSource(textBlock = """
        1, 10
        3, 30
        """)
    void pricePerQuantity(int quantity, int expected) {
        assertEquals(expected, calculator.price("pen", quantity));
    }

    @ParameterizedTest
    @ValueSource(ints = { -1, -100 })
    void rejectsNegativeQuantity(int quantity) {
        var e = assertThrows(IllegalArgumentException.class, () -> calculator.price("pen", quantity));
        assertEquals("quantity must be positive", e.getMessage());
    }

    @Test
    @Tag("slow")
    void exportsPriceList(@TempDir Path dir) throws Exception {
        Path file = calculator.export(dir);
        assertAll(
            () -> assertTrue(Files.exists(file)),
            () -> assertEquals("prices.csv", file.getFileName().toString()));
    }

    @Nested
    class WithDiscount {
        @BeforeEach
        void applyDiscount() {
            calculator.discount(10);
        }

        @Test
        void reducesPrice() {
            assertEquals(90, calculator.price("pen", 9));
        }
    }
}
