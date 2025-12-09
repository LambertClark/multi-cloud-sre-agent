# 华为云ECS监控指标

## 弹性云服务器监控指标

### CPU使用率
- **指标名称**: cpu_util
- **命名空间**: SYS.ECS
- **统计类型**: Average
- **单位**: %
- **查询示例**:
```json
{
  "cloud": "huawei",
  "resource": "ECS:{instance_id}",
  "type": "metric",
  "value": "{cpu_usage_percent}",
  "timestamp": "{timestamp}"
}
```

### 内存使用率
- **指标名称**: mem_util
- **单位**: %
- **统计类型**: Average

### 磁盘使用率
- **指标名称**: disk_util
- **单位**: %
- **统计类型**: Average

## ECS实例ID格式
华为云ECS实例ID格式: 16位UUID格式
例如: `12345678-90ab-cdef-1234-567890abcdef`

## 查询示例
"查华为云ECS 12345678-90ab-cdef-1234-567890abcdef的CPU使用率"

返回格式:
```json
{
  "cloud": "huawei",
  "resource": "ECS:12345678-90ab-cdef-1234-567890abcdef",
  "type": "metric",
  "value": 67.8,
  "timestamp": "2025-01-01T10:00:00Z"
}
```