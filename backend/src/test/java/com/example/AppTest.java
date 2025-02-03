package com.example;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest
public class AppTest {

    @Test
    void contextLoads() {
        assertThat(true).isTrue(); // Simple test to verify Spring context loads
    }
}
