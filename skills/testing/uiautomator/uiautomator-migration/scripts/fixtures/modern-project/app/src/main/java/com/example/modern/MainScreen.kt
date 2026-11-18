package com.example.modern

import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.testTagsAsResourceId

@Composable
fun MainScreen() {
    Scaffold(modifier = Modifier.semantics { testTagsAsResourceId = true }) { }
}
