# 腾讯云CVM监控指标

## 云服务器监控指标

### CPU使用率
- **指标名称**: CPUUsage
- **命名空间**: QCE/CVM
- **统计类型**: Average
- **单位**: %
- **查询示例**:
```json
{
  "cloud": "tencent",
  "resource": "CVM:ins-{instance_id}",
  "type": "metric",
  "value": "{cpu_usage_percent}",
  "timestamp": "{timestamp}"
}
```

### 内存使用率
- **指标名称**: MemoryUsage
- **单位**: %
- **统计类型**: Average

### 磁盘使用率
- **指标名称**: DiskUsage
- **单位**: %
- **统计类型**: Average

## CVM实例ID格式
腾讯云CVM实例ID格式: `ins-{13位数字}`
例如: `ins-1234567890123`

## 查询示例
"查腾讯云CVM ins-1234567890123的CPU使用率"

返回格式:
```json
{
  "cloud": "tencent",
  "resource": "CVM:ins-1234567890123",
  "type": "metric",
  "value": 82.3,
  "timestamp": "2025-01-01T10:00:00Z"
}
```