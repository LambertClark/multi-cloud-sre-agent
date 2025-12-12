# 多云SRE Agent - 待完成任务清单

## ✅ 已完成

- [x] **任务1：设计健康判断标准**
  - 创建统一的健康Schema (`schemas/health_schema.py`)
  - 定义HealthStatus枚举（healthy/degraded/unhealthy/critical/unknown）
  - 定义阈值配置（CPU/内存/日志错误率/Trace延迟等）
  - 支持MetricHealth、LogHealth、TraceHealth、ResourceHealth

- [x] **任务2：将Adapter重构为DataAdapterAgent**
  - 实现混合架构：规则引擎（快速路径）+ LLM引擎（智能路径）
  - 支持AWS EC2、CloudWatch Metric、X-Ray、Logs快速转换
  - 支持Kubernetes Pod快速转换
  - LLM智能转换兜底，零代码扩展新云平台
  - 创建完整测试用例和文档

---

## 📋 待完成任务

### 阶段一：基础功能完善

#### 任务3：实现业务标签到资源的映射机制
**目标：** 支持通过业务标签（如"xxx业务"）查询相关资源

**实现内容：**
- [ ] 创建 `TagMappingService` 类
- [ ] 实现 Tag → EC2实例 映射
- [ ] 实现 Tag → LogGroup 映射
- [ ] 实现 Tag → Pod/Namespace 映射
- [ ] 实现 Tag → CDN/ALB 映射
- [ ] 支持多云标签标准化（AWS Tags、K8s Labels、阿里云标签）

**涉及Agent：**
- Manager Agent（查询时使用）
- 新增 TagMappingAgent（可选）

**验证方式：**
```python
# 通过业务标签查询所有资源
resources = await tag_service.get_resources_by_tag("业务", "电商平台")
# 返回：所有标记为"电商平台"的EC2、Pod、LogGroup等
```

---

#### 任务4：实现批量查询EC2 CPU并过滤>80%的功能
**目标：** 简单模式场景1 - "列出全部CPU利用率超过80%的服务器"

**实现内容：**
- [ ] 扩展 `AWSMonitoringTools` 添加批量查询方法
- [ ] 实现 `batch_get_ec2_cpu_utilization(instance_ids, threshold)`
- [ ] 在 Manager Agent 中注册该功能
- [ ] 集成 DataAdapterAgent 转换为统一格式
- [ ] 支持Tag过滤（如：只查询特定业务的实例）

**流程：**
1. Manager Agent 解析请求 "列出CPU>80%的服务器"
2. 调用 `_list_ec2_instances_impl()` 获取实例列表
3. 批量查询各实例CPU（并行调用CloudWatch API）
4. DataAdapterAgent 转换为 MetricHealth
5. 过滤 CPU > 80% 的实例
6. 返回统一格式的结果

---

#### 任务5：实现Trace健康检查功能
**目标：** 简单模式场景2 - "帮我对xxx业务系统下的应用做个健康检查"

**实现内容：**
- [ ] 扩展 X-Ray 工具，支持按业务标签过滤
- [ ] 实现健康评分算法（基于错误率、P95延迟）
- [ ] 生成健康报告（包含问题列表和建议）
- [ ] 集成 DataAdapterAgent 转换为 TraceHealth

**健康判断标准：**
- 健康：错误率 < 1% 且 P95延迟 < 1s
- 降级：错误率 1-5% 或 P95延迟 1-3s
- 不健康：错误率 > 5% 或 P95延迟 > 3s

---

### 阶段二：困难模式功能

#### 任务6：集成Kubernetes/EKS工具
**目标：** 支持Pod级别的监控和管理

**实现内容：**
- [ ] 创建 `K8sTools` 类（`tools/k8s_tools.py`）
- [ ] 实现 `list_pods(namespace, labels)` - 列出Pod
- [ ] 实现 `describe_pod(namespace, name)` - 获取Pod详情和Events
- [ ] 实现 `get_pod_logs(namespace, name)` - 获取Pod日志
- [ ] 实现 `get_pod_metrics(namespace, name)` - 获取CPU/内存使用
- [ ] 注册到 CloudToolRegistry

**依赖：**
- 安装 `kubernetes` Python客户端
- 配置 kubeconfig 或使用AWS EKS凭证

---

#### 任务7：实现Pod健康状态判断功能
**目标：** 困难模式场景1 - "列出xxx业务中不健康的Pod"

**实现内容：**
- [ ] 定义Pod不健康状态（CrashLoopBackOff、Pending超时、OOMKilled等）
- [ ] 实现 `check_pod_health(pod_data)` 方法
- [ ] 支持按业务标签过滤Pod
- [ ] 返回 ResourceHealth 统一格式

**不健康判断标准：**
- CrashLoopBackOff 状态
- Pending 超过5分钟
- 重启次数 > 10
- OOMKilled 或 ImagePullBackOff

---

#### 任务8：集成CloudFront监控工具
**目标：** 困难模式场景2 - "列出缓存命中率<10%或耗时>1s的CDN服务"

**实现内容：**
- [ ] 扩展 `AWSMonitoringTools` 添加 CloudFront 支持
- [ ] 实现 `get_cloudfront_cache_hit_rate(distribution_id)`
- [ ] 实现 `get_cloudfront_latency(distribution_id)`
- [ ] 支持批量查询多个分发
- [ ] 按阈值过滤（缓存命中率<10%、延迟>1s）

**CloudFront指标：**
- CacheHitRate（缓存命中率）
- OriginLatency（源站延迟）
- 4xxErrorRate / 5xxErrorRate（错误率）

---

#### 任务9：实现日志巡查健康判断功能
**目标：** 困难模式场景3 - "帮我巡查最近一小时xxx业务相关的全部日志"

**实现内容：**
- [ ] 实现业务标签 → LogGroup 映射
- [ ] 批量查询多个LogGroup
- [ ] 统计ERROR/WARN/CRITICAL日志数量
- [ ] 计算错误率和健康评分
- [ ] 提取关键错误样本
- [ ] 生成健康报告

**健康评分算法：**
```
health_score = 100 - (error_rate * 1000) - (critical_count * 10)
```

---

#### 任务10：实现X-Ray详细trace获取
**目标：** 获取完整的trace调用链路

**实现内容：**
- [ ] 实现 `get_trace_graph(trace_id)` - 获取单个trace的完整调用图
- [ ] 解析trace segments和subsegments
- [ ] 构建服务调用依赖树
- [ ] 识别瓶颈节点（耗时最长的span）

**API：** AWS X-Ray `BatchGetTraces`

---

#### 任务11：实现Trace根因分析流程
**目标：** 困难模式场景4 - "帮我分析xxx应用异常的根本原因"

**实现内容：**
- [ ] 创建 `TraceAnalysisAgent`（LLM驱动）
- [ ] 获取异常trace的详细调用链
- [ ] LLM分析：
  - 识别错误发生的服务和方法
  - 分析错误传播路径
  - 找出最早出现错误的节点
  - 关联日志和指标数据
- [ ] 生成根因分析报告

**流程：**
1. Manager Agent 识别任务为"trace根因分析"
2. 调用 X-Ray 获取异常trace列表
3. 获取详细trace graph
4. 提取关键信息（错误节点、调用耗时、HTTP状态码）
5. TraceAnalysisAgent 调用LLM分析
6. 生成报告：根本原因 + 修复建议

---

### 阶段三：地狱模式功能

#### 任务12：集成AWS Cost Explorer工具
**目标：** 获取成本数据用于优化分析

**实现内容：**
- [ ] 创建 Cost Explorer 客户端
- [ ] 实现 `get_cost_by_service(start_date, end_date)`
- [ ] 实现 `get_cost_by_tag(tag_key, tag_value)`
- [ ] 实现 `get_rightsizing_recommendations()`
- [ ] 注册到工具集

**API：** AWS Cost Explorer API

---

#### 任务13：实现资源使用分析模块
**目标：** 地狱模式场景1 - "找出资源使用不合理的业务"

**实现内容：**
- [ ] 创建 `ResourceAnalysisAgent`
- [ ] 收集资源使用历史数据（CPU/内存/网络，最近7天）
- [ ] 识别低利用率资源（CPU<20%持续7天）
- [ ] 识别过度配置（内存限制远大于实际使用）
- [ ] 计算浪费成本
- [ ] 按业务聚合分析结果

**输出：**
```json
{
  "business": "电商平台",
  "total_resources": 50,
  "underutilized": 15,
  "wasted_cost_monthly": 1200.50,
  "recommendations": [...]
}
```

---

#### 任务14：实现LLM驱动的资源优化推荐功能
**目标：** 生成具体的优化方案

**实现内容：**
- [ ] 创建 `OptimizationAgent`（LLM驱动）
- [ ] 输入：资源使用数据 + 成本数据
- [ ] LLM分析：
  - Rightsizing建议（如：t3.large → t3.medium）
  - 预留实例购买建议
  - Spot实例使用建议
  - 资源调度优化（如：非工作时间关闭）
- [ ] 估算节省成本
- [ ] 生成优化方案文档

---

#### 任务15：实现Pod下钻诊断流程
**目标：** 地狱模式场景2 - "列出xxx业务中不健康的Pod，并下钻定位原因"

**实现内容：**
- [ ] 创建 `PodDiagnosticAgent`
- [ ] 多层诊断流程：
  1. **查询Pod状态** - 识别不健康Pod
  2. **获取Events** - `kubectl describe pod`
  3. **提取日志** - `kubectl logs`（包含前一个容器日志）
  4. **查询指标** - CPU/内存使用趋势
  5. **关联分析** - 节点状态、PVC状态、网络策略
- [ ] LLM综合分析所有数据
- [ ] 生成诊断报告（问题 + 根因 + 修复建议）

**诊断报告示例：**
```
Pod: web-app-5d7c8b9f4-xyz12
状态: CrashLoopBackOff

根本原因:
- OOMKilled（内存不足）
- 容器实际使用450MB，但limit设置为256MB

修复建议:
1. 增加memory limit至512MB
2. 检查应用是否存在内存泄漏
3. 考虑优化应用内存使用
```

---

### 阶段四：测试和完善

#### 任务16：编写集成测试用例验证所有场景

**测试用例清单：**
- [ ] **简单模式测试**
  - 测试：列出CPU>80%的EC2实例
  - 测试：Trace健康检查

- [ ] **困难模式测试**
  - 测试：列出不健康的Pod
  - 测试：CDN缓存命中率查询
  - 测试：日志巡查健康判断
  - 测试：Trace根因分析

- [ ] **地狱模式测试**
  - 测试：资源使用分析
  - 测试：优化方案生成
  - 测试：Pod下钻诊断

- [ ] **多云适配测试**
  - 测试：DataAdapterAgent转换AWS数据
  - 测试：DataAdapterAgent转换K8s数据
  - 测试：DataAdapterAgent LLM转换阿里云数据

- [ ] **端到端测试**
  - 测试：用户请求 → Manager Agent → 多步骤编排 → 返回结果
  - 测试：业务标签过滤功能
  - 测试：统一Schema返回

---

## 优先级排序

### P0 - 核心功能（必须完成）
1. 任务3：业务标签映射
2. 任务4：批量查询EC2 CPU
3. 任务6：集成K8s工具
4. 任务7：Pod健康判断

### P1 - 重要功能
5. 任务5：Trace健康检查
6. 任务8：CloudFront监控
7. 任务9：日志巡查健康判断

### P2 - 高级功能
8. 任务10-11：Trace根因分析
9. 任务12-14：成本优化
10. 任务15：Pod下钻诊断

### P3 - 测试完善
11. 任务16：集成测试

---

## 当前进度

```
总任务: 16
已完成: 2 (12.5%)
待完成: 14 (87.5%)

阶段一（基础）: 0/3 完成
阶段二（困难）: 0/6 完成
阶段三（地狱）: 0/4 完成
阶段四（测试）: 0/1 完成
```

---

## 下一步行动

**建议顺序：**
1. 先测试现有系统（DataAdapterAgent、Schema定义）
2. 完成任务3（业务标签映射）- 基础设施
3. 完成任务4（批量查询EC2 CPU）- 简单模式第一个场景
4. 完成任务6-7（K8s集成 + Pod健康判断）- 困难模式核心功能
5. 其余功能按优先级逐步实现
