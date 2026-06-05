package com.advisor.client;

import com.advisor.config.AdvisorConfig;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.RequestBody;
import okhttp3.Response;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

@Component
public class DataServiceClient {

    private final OkHttpClient httpClient;
    private final AdvisorConfig config;

    @Autowired
    public DataServiceClient(AdvisorConfig config) {
        this.config = config;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(10, TimeUnit.SECONDS)
                .readTimeout(30, TimeUnit.SECONDS)
                .build();
    }

    /**
     * 获取最新资讯
     */
    public List<JSONObject> getLatestNews(int limit) {
        String url = config.getDataServiceUrl() + "/api/news/latest?limit=" + limit;
        return requestList(url);
    }

    /**
     * 搜索资讯
     */
    public List<JSONObject> searchNews(String keyword, int limit) {
        String url = config.getDataServiceUrl() + "/api/news/search?keyword=" + keyword + "&limit=" + limit;
        return requestList(url);
    }

    /**
     * 获取今日选股
     */
    public List<JSONObject> getTodayScreening() {
        String url = config.getDataServiceUrl() + "/api/screening/today";
        return requestList(url);
    }

    /**
     * 获取推荐表现
     */
    public JSONObject getPerformance() {
        String url = config.getDataServiceUrl() + "/api/tracking/performance";
        return requestObject(url);
    }

    /**
     * 获取历史选股
     */
    public List<JSONObject> getHistoryScreening(String date) {
        String url = config.getDataServiceUrl() + "/api/screening/history?date=" + date;
        return requestList(url);
    }

    /**
     * 获取筛选规则
     */
    public List<JSONObject> getScreeningRules() {
        String url = config.getDataServiceUrl() + "/api/screening/rules";
        return requestList(url);
    }

    /**
     * 手动触发选股
     */
    public String triggerScreening() {
        String url = config.getDataServiceUrl() + "/api/screening/run";
        JSONObject result = postRequest(url);
        return result.getString("message");
    }

    /**
     * 获取 AI 建议规则
     */
    public List<JSONObject> getSuggestions() {
        String url = config.getDataServiceUrl() + "/api/learning/suggestions";
        return requestList(url);
    }

    /**
     * 审批规则
     */
    public String approveRule(Long ruleId) {
        String url = config.getDataServiceUrl() + "/api/learning/approve-rule?rule_id=" + ruleId;
        JSONObject result = postRequest(url);
        return result.getString("message");
    }

    /**
     * 拒绝规则
     */
    public String rejectRule(Long ruleId) {
        String url = config.getDataServiceUrl() + "/api/learning/reject-rule?rule_id=" + ruleId;
        JSONObject result = postRequest(url);
        return result.getString("message");
    }

    private List<JSONObject> requestList(String url) {
        try {
            Request request = new Request.Builder().url(url).get().build();
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    String body = response.body().string();
                    JSONObject json = JSON.parseObject(body);
                    JSONArray data = json.getJSONArray("data");
                    if (data != null) {
                        return data.toJavaList(JSONObject.class);
                    }
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return Collections.emptyList();
    }

    private JSONObject requestObject(String url) {
        try {
            Request request = new Request.Builder().url(url).get().build();
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    return JSON.parseObject(response.body().string());
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return new JSONObject();
    }

    private JSONObject postRequest(String url) {
        try {
            RequestBody body = RequestBody.create("", MediaType.parse("application/json"));
            Request request = new Request.Builder().url(url).post(body).build();
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    return JSON.parseObject(response.body().string());
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return new JSONObject();
    }
}
