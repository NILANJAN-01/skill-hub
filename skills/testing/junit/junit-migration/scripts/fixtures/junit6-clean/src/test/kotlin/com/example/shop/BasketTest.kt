package com.example.shop

import org.junit.jupiter.api.AfterAll
import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import org.junit.jupiter.params.ParameterizedTest
import org.junit.jupiter.params.provider.ValueSource
import kotlin.test.assertEquals

class BasketTest {

    companion object {
        private lateinit var catalog: Catalog

        @JvmStatic
        @BeforeAll
        fun loadCatalog() {
            catalog = Catalog.sample()
        }

        @JvmStatic
        @AfterAll
        fun closeCatalog() = catalog.close()
    }

    @Test
    fun `adds an item`() {
        val basket = Basket(catalog)
        basket.add("pen")
        assertEquals(1, basket.size)
    }

    @ParameterizedTest
    @ValueSource(strings = ["", " "])
    fun `rejects blank names`(name: String) {
        assertThrows<IllegalArgumentException> { Basket(catalog).add(name) }
    }

    @Test
    fun `is empty at first`() = assertEquals(0, Basket(catalog).size)

    @Nested
    inner class WhenFull {
        @Test
        fun `rejects more items`() {
            val basket = Basket(catalog, capacity = 1).apply { add("pen") }
            assertThrows<IllegalStateException> { basket.add("book") }
        }
    }
}
