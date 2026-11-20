package demo;

import java.util.List;

public class TextDocument {
    private TextArea textArea;
    private boolean syncStatus = true;

    public int getCursorOffset() {
        return textArea.getCursorOffset();
    }

    public void insertString(String textToInsert, int offset) {
        textArea.insertString(textToInsert, offset);
    }

    /**
     * Gets the line count.
     */
    public int getLineCount() {
        int count = 0;
        for (String line : textArea.lines()) {
            count++;
        }
        return count;
    }

    public Pair<Integer, Boolean> currentTerm(int a, int b, int c, int d, int e) {
        // Return a new pair
        return new Pair<Integer, Boolean>(a, false);
    }

    public void load(String path) {
        try {
            textArea.read(path);
        } catch (IOException e) {
        }
    }

    public void refresh() {
        int data = 0;
        textArea.redraw();
        textArea.redraw();
        textArea.redraw();
    }
}
