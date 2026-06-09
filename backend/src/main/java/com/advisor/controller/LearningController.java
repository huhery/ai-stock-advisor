package com.advisor.controller;

import com.advisor.client.DataServiceClient;
import com.advisor.common.Result;
import com.alibaba.fastjson2.JSONObject;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/learning")
@CrossOrigin(origins = "*")
public class LearningController {

    @Autowired
    private DataServiceClient dataServiceClient;

    @GetMapping("/performance")
    public Result<JSONObject> getPerformance() {
        return Result.success(dataServiceClient.getPerformance());
    }

    @GetMapping("/suggestions")
    public Result<List<JSONObject>> getSuggestions() {
        return Result.success(dataServiceClient.getSuggestions());
    }

    @PostMapping("/approve-rule")
    public Result<String> approveRule(@RequestParam Long ruleId) {
        return Result.success(dataServiceClient.approveRule(ruleId));
    }

    @PostMapping("/reject-rule")
    public Result<String> rejectRule(@RequestParam Long ruleId) {
        return Result.success(dataServiceClient.rejectRule(ruleId));
    }
}
