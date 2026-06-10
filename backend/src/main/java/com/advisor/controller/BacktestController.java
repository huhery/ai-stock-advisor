package com.advisor.controller;

import com.advisor.common.Result;
import com.advisor.config.AdvisorConfig;
import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import okhttp3.MediaType;
import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.Response;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.concurrent.TimeUnit;

@RestController
@RequestMapping("/api/backtest")
@CrossOrigin(origins = "*")
public class BacktestController {

    private final OkHttpClient httpClient;
    private final AdvisorConfig config;

    @Autowired
    public BacktestController(AdvisorConfig config) {
        this.config = config;
        this.httpClient = new OkHttpClient.Builder()
                .connectTimeout(30, TimeUnit.SECONDS)
                .readTimeout(1800, TimeUnit.SECONDS) // 30分钟超时
                .build();
    }

    @GetMapping("/periods")
    public Result<JSONObject> getPeriods() {
        String url = config.getDataServiceUrl() + "/api/backtest/periods";
        return Result.success(doGet(url));
    }

    @PostMapping("/run")
    public Result<JSONObject> runBacktest(
            @RequestParam(defaultValue = "20") int generations,
            @RequestParam(defaultValue = "65") double target_win_rate,
            @RequestParam(defaultValue = "5") double target_avg_return,
            @RequestParam(required = false) String periods) {
        String url = config.getDataServiceUrl() + "/api/backtest/run"
                + "?generations=" + generations
                + "&target_win_rate=" + target_win_rate
                + "&target_avg_return=" + target_avg_return;
        if (periods != null && !periods.isEmpty()) {
            url += "&periods=" + periods;
        }
        return Result.success(doPost(url));
    }

    @PostMapping("/apply")
    public Result<JSONObject> applyBacktest(
            @RequestParam(required = false) Integer backtest_id) {
        String url = config.getDataServiceUrl() + "/api/backtest/apply";
        if (backtest_id != null) {
            url += "?backtest_id=" + backtest_id;
        }
        return Result.success(doPost(url));
    }

    @GetMapping("/history")
    public Result<JSONObject> getHistory() {
        String url = config.getDataServiceUrl() + "/api/backtest/history";
        return Result.success(doGet(url));
    }

    @GetMapping("/status")
    public Result<JSONObject> getStatus() {
        String url = config.getDataServiceUrl() + "/api/backtest/status";
        return Result.success(doGet(url));
    }

    private JSONObject doGet(String url) {
        try {
            Request request = new Request.Builder().url(url).get().build();
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    byte[] bytes = response.body().bytes();
                    String respStr = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
                    return JSON.parseObject(respStr);
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return new JSONObject();
    }

    private JSONObject doPost(String url) {
        try {
            okhttp3.RequestBody body = okhttp3.RequestBody.create("", MediaType.parse("application/json"));
            Request request = new Request.Builder().url(url).post(body).build();
            try (Response response = httpClient.newCall(request).execute()) {
                if (response.isSuccessful() && response.body() != null) {
                    byte[] bytes = response.body().bytes();
                    String respStr = new String(bytes, java.nio.charset.StandardCharsets.UTF_8);
                    return JSON.parseObject(respStr);
                }
            }
        } catch (IOException e) {
            e.printStackTrace();
        }
        return new JSONObject();
    }
}
