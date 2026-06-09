package com.advisor.service;

import com.advisor.client.DataServiceClient;
import com.advisor.client.LlmClient;
import com.advisor.mapper.ChatHistoryMapper;
import com.advisor.model.ChatHistory;
import com.alibaba.fastjson2.JSONObject;
import com.baomidou.mybatisplus.core.conditions.query.QueryWrapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.Date;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class ChatService {

    @Autowired
    private LlmClient llmClient;

    @Autowired
    private DataServiceClient dataServiceClient;

    @Autowired
    private ChatHistoryMapper chatHistoryMapper;

    /**
     * 处理用户消息，返回 AI 回复
     */
    public String chat(String userMessage) {
        // 1. 获取最新资讯作为上下文
        String contextData = buildContext(userMessage);

        // 2. 调用大模型
        String reply = llmClient.chat(userMessage, contextData);

        // 3. 保存对话历史
        saveHistory("user", userMessage, null);
        saveHistory("assistant", reply, contextData);

        return reply;
    }

    /**
     * 获取对话历史
     */
    public List<ChatHistory> getHistory(int limit) {
        QueryWrapper<ChatHistory> wrapper = new QueryWrapper<>();
        wrapper.orderByDesc("created_at").last("LIMIT " + limit);
        List<ChatHistory> list = chatHistoryMapper.selectList(wrapper);
        // 反转为时间正序
        java.util.Collections.reverse(list);
        return list;
    }

    /**
     * 构建上下文信息
     */
    private String buildContext(String userMessage) {
        StringBuilder context = new StringBuilder();

        // 获取最新政策
        List<JSONObject> news = dataServiceClient.getLatestNews(5);
        if (!news.isEmpty()) {
            context.append("【最新政策资讯】\n");
            for (JSONObject n : news) {
                context.append("- ").append(n.getString("title"))
                       .append("（").append(n.getString("source")).append("）\n");
            }
            context.append("\n");
        }

        // 如果消息中提到了关键词，搜索相关资讯
        if (userMessage.length() > 2) {
            List<JSONObject> related = dataServiceClient.searchNews(userMessage, 3);
            if (!related.isEmpty()) {
                context.append("【相关资讯】\n");
                for (JSONObject r : related) {
                    context.append("- ").append(r.getString("title")).append("\n");
                }
                context.append("\n");
            }
        }

        return context.toString();
    }

    private void saveHistory(String role, String content, String contextData) {
        ChatHistory history = new ChatHistory();
        history.setRole(role);
        history.setContent(content);
        history.setContextData(contextData);
        history.setCreatedAt(new Date());
        chatHistoryMapper.insert(history);
    }
}
