package com.advisor.controller;

import com.advisor.client.DataServiceClient;
import com.advisor.common.Result;
import com.alibaba.fastjson2.JSONObject;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/screening")
@CrossOrigin(origins = "*")
public class ScreeningController {

    @Autowired
    private DataServiceClient dataServiceClient;

    @GetMapping("/today")
    public Result<List<JSONObject>> getToday() {
        return Result.success(dataServiceClient.getTodayScreening());
    }

    @GetMapping("/history")
    public Result<List<JSONObject>> getHistory(@RequestParam String date) {
        return Result.success(dataServiceClient.getHistoryScreening(date));
    }

    @GetMapping("/rules")
    public Result<List<JSONObject>> getRules() {
        return Result.success(dataServiceClient.getScreeningRules());
    }

    @PostMapping("/run")
    public Result<String> triggerRun() {
        return Result.success(dataServiceClient.triggerScreening());
    }
}
