package com.advisor.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

@Data
@Configuration
@ConfigurationProperties(prefix = "advisor")
public class AdvisorConfig {

    private String dataServiceUrl;
    private Llm llm = new Llm();

    @Data
    public static class Llm {
        private String apiKey;
        private String baseUrl;
        private String model;
    }
}
