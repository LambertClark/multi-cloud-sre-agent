# AWS EC2 监控指标

## 基础监控指标

### CPU使用率指标
- **指标名称**: CPUUtilization
- **命名空间**: AWS/EC2
- **统计类型**: Average
- **单位**: Percent
- **查询示例**: 
```json
{
  "cloud": "aws",
  "resource": "EC2:i-{instance_id}",
  "type": "metric",
  "value": "{cpu_usage_percent}",
  "timestamp": "{timestamp}"
}
```

### 内存使用率指标
- **指标名称**: MemoryUtilization
- **命名空间**: System/Linux
- **统计类型**: Average
- **单位**: Percent
- **要求**: 需要安装CloudWatch代理

### 网络流量指标
- **入站流量**: NetworkIn
- **出站流量**: NetworkOut
- **单位**: Bytes
- **统计类型**: Sum/Average

## 实例ID格式
AWS EC2实例ID格式: `i-{17位字符}`
例如: `i-1234567890abcdef0`

## 查询示例
"查AWS EC2 i-1234567890abcdef0的CPU使用率"

返回格式:
```json
{
  "cloud": "aws",
  "resource": "EC2:i-1234567890abcdef0",
  "type": "metric",
  "value": 75.5,
  "timestamp": "2025-01-01T10:00:00Z"
}
```