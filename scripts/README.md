# scripts

Windows 自动运行脚本。

## run_daily.bat

功能：执行完整日报流程。

```bat
python main.py daily
```

脚本会自动切换到项目根目录，因此可以从任何位置运行：

```powershell
C:\AI-Tech-Radar\scripts\run_daily.bat
```

日志位置：

- `logs/app.log`：应用 INFO 日志
- `logs/error.log`：应用 ERROR 日志
- `logs/daily_console.log`：批处理运行时的控制台输出

## Windows 任务计划配置步骤

1. 打开“任务计划程序”
2. 选择“创建基本任务”
3. 名称填写 `AI Tech Radar Daily`
4. 触发器选择“每天”，设置执行时间
5. 操作选择“启动程序”
6. 程序或脚本填写：

```text
C:\AI-Tech-Radar\scripts\run_daily.bat
```

7. “起始于”填写：

```text
C:\AI-Tech-Radar
```

8. 完成创建后，可右键任务选择“运行”进行测试
