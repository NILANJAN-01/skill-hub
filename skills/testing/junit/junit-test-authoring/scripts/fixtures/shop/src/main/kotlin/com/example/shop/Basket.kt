package com.example.shop

/** Sample class used by the scaffold tests. */
class Basket(private val catalog: Map<String, Int>, val capacity: Int = 10) {

    private val items = mutableListOf<String>()

    val size: Int get() = items.size

    fun add(item: String) {
        require(item.isNotBlank()) { "item must not be blank" }
        check(items.size < capacity) { "basket is full" }
        items += item
    }

    fun total(): Int = items.sumOf { catalog.getValue(it) }

    fun priceOf(item: String, quantity: Int): Int {
        if (quantity <= 0) throw IllegalArgumentException("quantity must be positive")
        return catalog.getValue(item) * quantity
    }

    suspend fun checkout(): String = "order-${items.size}"

    private fun clear() = items.clear()

    companion object {
        fun empty(): Basket = Basket(emptyMap())
    }
}
