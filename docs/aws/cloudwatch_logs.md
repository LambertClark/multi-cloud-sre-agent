# AWS CloudWatch 日志

## 日志组结构
- **日志组名称**: /aws/ec2/{instance_id}
- **日志流名称**: {instance_id}/cloud-init-output.log

## 日志格式
```json
{
  "timestamp": 1704110400000,
  "message": "EC2 instance startup completed",
  "ingestionTime": 1704110401000
}
```

## 查询语法
- **字段查询**: `@message = "error"`
- **时间范围**: `@timestamp >= 1704110400000`
- **过滤示例**: `filter @message like /ERROR|CRITICAL/`

## 日志查询MCP格式
```json
{
  "cloud": "aws",
  "resource": "CloudWatch:/aws/ec2/{instance_id}",
  "type": "log",
  "value": "{log_message}",
  "timestamp": "{timestamp}"
}
```