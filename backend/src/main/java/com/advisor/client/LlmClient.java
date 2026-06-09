package com.advisor.client;

import com.advisor.config.AdvisorConfig;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import okhttp3.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

@Component
public class LlmClient {

    private static final String SYSTEM_PROMPT =
            "你是一位资深A股投资顾问，拥有20年实战经验。\n" +
            "你擅长政策解读、技术面分析、基本面分析和资金面分析。\n" +
            "你的建议专业、直接，会给出明确的观点和操作方向。\n" +
            "回答时遵循：1. 先分析逻辑和依据 2. 给出明确结论 3. 提示风险点\n" +
            "如果用户问到具体股票，结合提供的行情数据和政策信息进行分析。\n" +
            "注意：你的建议仅供参考，需提醒用户投资有风险。";

    private static final MediaType JSON_TYPE = MediaType.parse("application/json");

    private final OkHttpClient httpClient;
    private final AdvisorConfig config;

    @Autowired
    public LlmClient(AdvisorConfig config) {
        this.config = config;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(60, TimeUnit.SECONDS)
                .build();
    }

    /**
     * 发送对话请求
     *
     * @param userMessage 用户消息
     * @param contextData 上下文数据（最新政策、行情等）
     * @return AI 回复文本
     */
    public String chat(String userMessage, String contextData) {
        JSONArray messages = new JSONArray();

        // System prompt
        JSONObject systemMsg = new JSONObject();
        systemMsg.put("role", "system");
        String systemContent = SYSTEM_PROMPT;
        if (contextData != null && !contextData.isEmpty()) {
            systemContent += "\n\n以下是当前市场相关信息供你参考：\n" + contextData;
        }
        systemMsg.put("content", systemContent);
        messages.add(systemMsg);

        // User message
        JSONObject userMsg = new JSONObject();
        userMsg.put("role", "user");
        userMsg.put("content", userMessage);
        messages.add(userMsg);

        // Build request body
        JSONObject body = new JSONObject();
        body.put("model", config.getLlm().getModel());
        body.put("messages", messages);
        body.put("temperature", 0.7);
        body.put("max_tokens", 2000);

        Request request = new Request.Builder()
                .url(config.getLlm().getBaseUrl() + "/chat/completions")
                .header("Authorization", "Bearer " + config.getLlm().getApiKey())
                .header("Content-Type", "application/json")
                .post(RequestBody.create(body.toJSONString(), JSON_TYPE))
                .build();

        try (Response response = httpClient.newCall(request).execute()) {
            if (response.isSuccessful() && response.body() != null) {
                String responseBody = response.body().string();
                JSONObject json = JSON.parseObject(responseBody);
                JSONArray choices = json.getJSONArray("choices");
                if (choices != null && !choices.isEmpty()) {
                    return choices.getJSONObject(0)
                            .getJSONObject("message")
                            .getString("content");
                }
            } else {
                String errorBody = response.body() != null ? response.body().string() : "unknown error";
                return "AI 服务暂时不可用，请稍后重试。错误信息：" + errorBody;
            }
        } catch (IOException e) {
            return "网络错误，无法连接 AI 服务：" + e.getMessage();
        }
        return "未能获取 AI 回复，请重试。";
    }
}
