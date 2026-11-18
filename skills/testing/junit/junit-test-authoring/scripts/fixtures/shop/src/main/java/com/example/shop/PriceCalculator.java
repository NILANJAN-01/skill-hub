package com.example.shop;

import java.util.List;
import java.util.Map;

/** Sample class used by the scaffold tests. */
public class PriceCalculator {

    private final Map<String, Integer> prices;
    private int discountPercent;

    public PriceCalculator(Map<String, Integer> prices) {
        this.prices = prices;
    }

    public int price(String item, int quantity) {
        if (quantity <= 0) {
            throw new IllegalArgumentException("quantity must be positive");
        }
        Integer unit = prices.get(item);
        if (unit == null) {
            throw new UnknownItemException(item);
        }
        return unit * quantity * (100 - discountPercent) / 100;
    }

    public void discount(int percent) {
        this.discountPercent = percent;
    }

    public double gross(double net) {
        return net * 1.2;
    }

    public List<String> items() {
        return List.copyOf(prices.keySet());
    }

    public static int round(double value) {
        return (int) Math.round(value);
    }

    private void log(String message) {
        System.out.println(message);
    }

    /** Thrown for items that are not in the price list. */
    public static class UnknownItemException extends RuntimeException {
        public UnknownItemException(String item) {
            super("unknown item: " + item);
        }
    }
}
