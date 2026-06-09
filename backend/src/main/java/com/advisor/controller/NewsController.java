package com.advisor.controller;

import com.advisor.client.DataServiceClient;
import com.advisor.common.Result;
import com.alibaba.fastjson2.JSONObject;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/news")
@CrossOrigin(origins = "*")
public class NewsController {

    @Autowired
    private DataServiceClient dataServiceClient;

    @GetMapping("/latest")
    public Result<List<JSONObject>> getLatest(
            @RequestParam(defaultValue = "20") int limit) {
        return Result.success(dataServiceClient.getLatestNews(limit));
    }

    @GetMapping("/search")
    public Result<List<JSONObject>> search(
            @RequestParam String keyword,
            @RequestParam(defaultValue = "20") int limit) {
        return Result.success(dataServiceClient.searchNews(keyword, limit));
    }
}
