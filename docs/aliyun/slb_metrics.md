# 阿里云SLB监控指标

## 负载均衡指标

### QPS指标
- **指标名称**: QPS
- **命名空间**: acs_slb_dashboard
- **统计类型**: Average
- **单位**: Count/Second
- **查询示例**:
```json
{
  "cloud": "aliyun",
  "resource": "SLB:lb-{instance_id}",
  "type": "metric",
  "value": "{qps_value}",
  "timestamp": "{timestamp}"
}
```

### 响应时间指标
- **指标名称**: ResponseTime
- **单位**: ms
- **统计类型**: Average

### 连接数指标
- **活跃连接**: ActiveConnection
- **新建连接**: NewConnection
- **单位**: Count

## SLB实例ID格式
阿里云SLB实例ID格式: `lb-{16位字符}`
例如: `lb-1234567890abcdef`

## 查询示例
"查阿里云SLB lb-1234567890abcdef的QPS"

返回格式:
```json
{
  "cloud": "aliyun",
  "resource": "SLB:lb-1234567890abcdef",
  "type": "metric",
  "value": 1250,
  "timestamp": "2025-01-01T10:00:00Z"
}
```