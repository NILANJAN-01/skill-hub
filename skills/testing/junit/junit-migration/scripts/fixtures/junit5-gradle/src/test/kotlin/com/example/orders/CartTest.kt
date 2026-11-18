package com.example.orders

import org.junit.jupiter.api.BeforeAll
import org.junit.jupiter.api.Nested
import org.junit.jupiter.api.Test
import org.junit.jupiter.api.assertThrows
import kotlin.test.assertEquals

class CartTest {

    @BeforeAll
    fun setUpAll() {
        println("starting")
    }

    @Test
    fun `adds an item`() {
        val cart = Cart()
        cart.add("book")
        assertEquals(1, cart.size)
    }

    @Test
    fun `rejects blank items`() {
        assertThrows<IllegalArgumentException> { Cart().add(" ") }
    }

    @Test
    fun `computes nothing`() {
        Cart().add("pen")
    }

    @Nested
    class WhenEmpty {
        @Test
        fun `has size zero`() = assertEquals(0, Cart().size)
    }
}
