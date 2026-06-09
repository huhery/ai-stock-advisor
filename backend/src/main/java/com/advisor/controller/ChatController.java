package com.advisor.controller;

import com.advisor.common.Result;
import com.advisor.model.ChatHistory;
import com.advisor.service.ChatService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/chat")
@CrossOrigin(origins = "*")
public class ChatController {

    @Autowired
    private ChatService chatService;

    @PostMapping("/send")
    public Result<String> send(@RequestBody Map<String, String> request) {
        String message = request.get("message");
        if (message == null || message.trim().isEmpty()) {
            return Result.error("消息不能为空");
        }
        String reply = chatService.chat(message.trim());
        return Result.success(reply);
    }

    @GetMapping("/history")
    public Result<List<ChatHistory>> history(
            @RequestParam(defaultValue = "50") int limit) {
        return Result.success(chatService.getHistory(limit));
    }
}
