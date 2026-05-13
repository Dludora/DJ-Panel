# DJ Panel CLI Reference

This document describes the current `dj-panel` CLI from the codebase as it exists today.
It focuses on command hierarchy, responsibilities at each layer, common workflows, and
how defaults are resolved.

For runtime environment variables and code-level defaults, also see
[ENVIRONMENT_VARIABLES.md](./ENVIRONMENT_VARIABLES.md).

---

## 中文

### 1. CLI 总览

`dj-panel` 是当前后端项目的统一命令行入口，主要覆盖六个层级：

1. 启动层：启动后端服务与 Web 开发服务
2. 本地配置层：保存默认的 `workspace`、`user`、`base-url`
3. 团队协作层：管理工作空间与成员
4. Recipe 管理层：导入、查看、发布 Data-Juicer recipe
5. 运行提交层：基于 recipe version 创建一次 run submission
6. Worker 执行层：启动 Data-Juicer、training、evaluation worker，持续认领并执行任务

### 1.1 默认值来源

CLI 的默认值来源优先级如下：

1. 显式命令行参数
2. 本地 CLI 配置 `DJ_PANEL_CLI_CONFIG_PATH` 指向的文件
3. 环境变量
4. `app/config.py` 中的代码默认值

其中：

- `workspace`、`user`、`base-url` 这类用户习惯型默认值，通常通过本地 CLI 配置维护
- `host`、`port`、`database-url`、`workdir`、`dj-bin` 这类运行时默认值，统一通过环境变量和 `app/config.py` 管理

当前命令树如下：

```text
dj-panel
├── master
├── web
├── config
│   ├── set
│   └── show
├── workspace
│   ├── create
│   ├── list
│   └── members
│       ├── add
│       └── list
├── recipe
│   ├── import
│   ├── list
│   ├── show
│   └── publish
├── run
│   ├── submit
│   ├── list
│   ├── show
│   ├── resume
│   ├── cancel
│   └── logs
└── worker
    ├── dj
    ├── train
    └── eval
```

### 2. 顶层命令说明

#### `dj-panel master`

作用：
- 启动 DJ Panel backend 的 FastAPI 服务
- 可在启动前自动执行 Alembic migration
- 开发模式下可开启 `uvicorn --reload`

常见参数：
- `--host`：服务监听地址，默认 `127.0.0.1`
- `--port`：服务端口，默认 `8000`
- `--database-url`：数据库连接串，会写入 `DATABASE_URL`
- `--migrate`：启动前执行 `alembic upgrade head`
- `--reload`：开发时开启热重载

当前支持：
- PostgreSQL
- SQLite

典型用法：

```bash
dj-panel master --database-url postgresql+psycopg://user:pass@localhost:5432/dj_panel --migrate
```

SQLite 示例：

```bash
dj-panel master --database-url sqlite:///./dj_panel.db --migrate
```

#### `dj-panel web`

作用：
- 启动 `dj-panel-web` 的前端开发服务
- 将 backend 地址通过环境变量注入前端
- 可选自动安装前端依赖

常见参数：
- `--backend-url`：前端请求的 backend 地址
- `--host`：前端 dev server 监听地址，默认 `127.0.0.1`
- `--port`：前端 dev server 端口，默认 `1337`
- `--web-dir`：前端工程目录，默认自动定位 `dj-panel-web`
- `--npm-bin`：`npm` 可执行文件名，默认 `npm`
- `--install-deps`：启动前先执行 `npm install`
- `--open`：启动时自动打开浏览器

典型用法：

```bash
dj-panel web --backend-url http://127.0.0.1:8000 --install-deps
```

#### `dj-panel config`

作用：
- 维护 CLI 的本地默认配置
- 避免每个命令都重复传 `--workspace`、`--user`、`--base-url`

本地配置文件默认位置：

```text
~/.config/dj-panel/config.json
```

这个路径也可以通过 `DJ_PANEL_CLI_CONFIG_PATH` 改写。

##### `dj-panel config set`

作用：
- 设置默认 `workspace`
- 设置默认 `user`
- 设置默认 `base-url`

常见参数：
- `--workspace`
- `--user`
- `--base-url`
- `--json`

示例：

```bash
dj-panel config set --workspace llm-team --user alice --base-url http://127.0.0.1:8000
```

##### `dj-panel config show`

作用：
- 查看当前 CLI 默认配置

示例：

```bash
dj-panel config show
```

### 3. 工作空间层

#### `dj-panel workspace create`

作用：
- 创建一个 workspace
- 可选把这个 workspace 直接设为本地默认 workspace

常见参数：
- `slug`：workspace 的唯一标识
- `--name`：展示名称，默认同 `slug`
- `--description`
- `--owner`
- `--use`：创建后写入本地 config
- `--base-url`
- `--json`

示例：

```bash
dj-panel workspace create llm-team --name "LLM Team" --owner alice --use
```

#### `dj-panel workspace list`

作用：
- 列出 backend 当前已有的 workspace

示例：

```bash
dj-panel workspace list
```

#### `dj-panel workspace members add`

作用：
- 向某个 workspace 添加成员，或更新成员角色

常见参数：
- `--workspace`
- `--user`
- `--role`

支持角色：
- `OWNER`
- `MAINTAINER`
- `MEMBER`
- `VIEWER`

示例：

```bash
dj-panel workspace members add --workspace llm-team --user bob --role MEMBER
```

#### `dj-panel workspace members list`

作用：
- 查看某个 workspace 下的成员列表

示例：

```bash
dj-panel workspace members list --workspace llm-team
```

### 4. Recipe 管理层

这一层围绕 Data-Juicer recipe YAML 展开。

#### `dj-panel recipe import`

作用：
- 从本地 YAML 文件创建一个新的 recipe
- 首次把 recipe 纳入平台管理

常见参数：
- `file`：本地 YAML 文件路径
- `--workspace`
- `--owner`
- `--name`：recipe 名称；不传时优先使用 YAML 中的 `project_name`，否则使用文件名
- `--description`
- `--command`：默认 `dj-process --config recipe.yaml`
- `--timeout-seconds`
- `--extra-execution-spec`：附加合并到 `executionSpec` 的 JSON
- `--json`

CLI 内部会自动构造：
- `recipeBody`
- `scriptPath`
- `parameterSchema`
- `envTemplate`
- `executionSpec`
- `timeoutSeconds`

示例：

```bash
dj-panel recipe import ./config_lineage.yaml --workspace llm-team --name lineage_base --owner alice
```

#### `dj-panel recipe list`

作用：
- 列出某个 workspace 下的 recipes

示例：

```bash
dj-panel recipe list --workspace llm-team
```

#### `dj-panel recipe show`

作用：
- 查看某个 recipe 的详情
- 支持通过 `recipe id` 查询
- 也支持通过 `workspace + recipe name` 查询

查询方式一：

```bash
dj-panel recipe show --recipe-id <recipe-id>
```

查询方式二：

```bash
dj-panel recipe show --workspace llm-team --recipe lineage_base
```

#### `dj-panel recipe publish`

作用：
- 为一个已存在的 recipe 发布新版本
- 常用于更新 YAML、修改处理链路、发布新的 recipe version

常见参数：
- `file`
- `--workspace`
- `--recipe`：已存在的 recipe 名称
- `--owner`
- `--description`
- `--command`
- `--timeout-seconds`
- `--extra-execution-spec`
- `--json`

示例：

```bash
dj-panel recipe publish ./config_lineage_v2.yaml --workspace llm-team --recipe lineage_base --owner alice
```

### 5. 运行提交层

#### `dj-panel run submit`

作用：
- 创建一次 `run submission`
- 它表示“用户希望平台发起一次 processing、training 或 evaluation 运行”
- 提交成功后，后端会基于 submission 展开可认领的 task

常见参数：
- `--workspace`
- `--kind`：支持 `processing`、`training`、`evaluation`
- `--requested-by`
- `--parameters`：JSON 字符串或 JSON 文件路径；当前只保留给 command-based `training` / `evaluation`
- `--spec`：YAML/JSON 对象或文件路径；`processing`、`training`、`evaluation` 都通过它描述提交内容
- `--name`
- `--json`

注意：
- 当 `--kind processing` 时：
  需要 `--spec`
- 当 `--kind training` 或 `--kind evaluation` 时：
  需要 `--spec`
- processing 的第一版 spec 使用 DJ Panel 自己的高层格式，重点字段在：
  - `kind`
  - `name`
  - `requestedBy`
  - `process.dj_configs`
  - `process.extra_configs`
  - `process.env`
  - `process.timeoutSeconds`

示例：

```bash
dj-panel run submit \
  --workspace llm-team \
  --kind processing \
  --spec ./process_spec.yaml \
  --requested-by alice
```

training 示例：

```bash
dj-panel run submit \
  --workspace llm-team \
  --kind training \
  --spec ./train_spec.yaml \
  --requested-by alice
```

evaluation 示例：

```bash
dj-panel run submit \
  --workspace llm-team \
  --kind evaluation \
  --spec ./eval_spec.yaml \
  --requested-by alice
```

`train_spec.yaml` 最小示例：

```yaml
name: qwen2-sft-v1
command: python train.py --config train.yaml
workdir: /mnt/team-repos/llm-trainer
env:
  MLFLOW_TRACKING_URI: http://127.0.0.1:5000
  MLFLOW_EXPERIMENT_NAME: qwen2-sft
timeoutSeconds: 7200
inputs:
  - uri: /data/processed/train.jsonl
outputs:
  - uri: /data/models/qwen2-sft-v1
```

`process_spec.yaml` 最小示例：

```yaml
kind: processing
name: demo-process-run
requestedBy: alice
process:
  dj_configs:
    mode: workspace_recipe
    name: lineage_base
  extra_configs:
    dataset_path: /data/raw/train.jsonl
    export_path: /data/processed/train.jsonl
  env:
    OPENLINEAGE_URL: http://127.0.0.1:8000/api/v1/lineage
  timeoutSeconds: 7200
```

processing 当前还支持：
- `process.dj_configs.mode = workspace_recipe`
- `process.dj_configs.mode = local_file`

其中 `local_file` 模式下：
- CLI 会先本地解析 YAML
- 然后把 `recipeBody` 嵌入提交 payload
- worker 最终会把 `recipeBody`、submission `parameters` 和平台注入的 `work_dir` 合并成 panel 侧 `recipe.yaml`

#### `dj-panel run list`

作用：
- 查看某个 workspace 下的 run submissions

#### `dj-panel run show`

作用：
- 查看单个 run submission 的详情

#### `dj-panel run resume`

作用：
- 恢复一个 `FAILED` 或 `CANCELLED` 的 run submission
- 保留原有 `task_id`
- 让 worker 后续基于同一个 DJ `job_id/work_dir` 创建新的 attempt

当前限制：
- 只支持 `FAILED` / `CANCELLED`
- 不会创建新的 task，而是把原 task 重置回 `PENDING`

示例：

```bash
dj-panel run resume c42b30c2-8a86-43c4-a97d-bff1849ce1e7
```

#### `dj-panel run cancel`

作用：
- 取消一个 `PENDING` 的 run submission
- 会把对应 `run_submission` 和派生的 `task` 一起改成 `CANCELLED`

当前限制：
- 只支持 `PENDING`
- 不处理中断已认领或运行中的 worker 进程

示例：

```bash
dj-panel run cancel bf3ea467-5805-46cd-a4b1-07df88242b97
```

#### `dj-panel run logs`

作用：
- 预留命令

当前状态：
- 尚未实现
```

### 6. Worker 执行层

#### `dj-panel worker dj`

作用：
- 启动一个 Data-Juicer worker
- 注册 worker
- 周期性上报 heartbeat
- 认领 `dj_recipe` 类型任务
- 将 submission 中的参数合并进 recipe，生成本地 `recipe.yaml`
- 运行 `dj-process`
- 注册日志文件 artifact、其他 artifact 和任务状态

常见参数：
- `--base-url`
- `--workspace`
- `--worker-id`
- `--display-name`
- `--workdir`
- `--dj-bin`
- `--poll-interval`

关键行为：

1. 调用 worker register 接口注册自己
2. 调用 heartbeat 接口更新状态
3. 调用 task claim 接口只认领 `taskKind = dj_recipe`
4. 在 `<workdir>/tasks/<task_id>/recipe.yaml` 物化本次运行配置
5. 执行类似命令：

```bash
dj-process --config /.../tasks/<task_id>/recipe.yaml --job_id <task_id>
```

6. 使用同一个 `<workdir>/tasks/<task_id>` 作为 DJ 的最终 `work_dir`
7. 把执行输出写入 `<workdir>/tasks/<task_id>/run.log`，并把它注册为 `LOG` artifact
8. 把 panel 物化后的 `recipe.yaml` 作为 `CONFIG` artifact 上报
9. 根据执行结果调用 `start` / `complete` / `fail`

目录语义固定为：
- `task_id == DJ job_id`
- `task_dir = <workdir>/tasks/<task_id>`
- worker 在 `cwd=task_dir` 下执行 DJ CLI
- DJ 的最终 `work_dir` 与这个 `task_dir` 对齐
- panel 侧文件是：
  - `recipe.yaml`
  - `run.log`
- DJ 侧运行态文件通常包括：
  - `cli.yaml`
  - `events_*.jsonl`
  - `logs/`
  - `ckpt/checkpoints`
  - `processed.jsonl`
  - `metadata/`

单次执行模式：
- `--poll-interval <= 0` 时只尝试认领一次

轮询模式：
- `--poll-interval > 0` 时持续循环认领任务

示例：

```bash
dj-panel worker dj \
  --workspace llm-team \
  --worker-id dj-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /Users/dludora/Code/data-juicer \
  --dj-bin dj-process \
  --poll-interval 5
```

#### `dj-panel worker train`

作用：
- 启动一个 command-based training worker
- 注册 worker
- 周期性上报 heartbeat
- 认领 `training` 类型任务
- 在 task 指定的 `workdir` 中直接执行 `command`
- 注册日志文件 artifact 并更新任务状态

常见参数：
- `--base-url`
- `--workspace`
- `--worker-id`
- `--display-name`
- `--workdir`
- `--poll-interval`

示例：

```bash
dj-panel worker train \
  --workspace llm-team \
  --worker-id train-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-train-worker \
  --poll-interval 5
```

#### `dj-panel worker eval`

作用：
- 启动一个 command-based evaluation worker
- 注册 worker
- 周期性上报 heartbeat
- 认领 `evaluation` 类型任务
- 在 task 指定的 `workdir` 中直接执行 `command`
- 注册日志文件 artifact 并更新任务状态

常见参数：
- `--base-url`
- `--workspace`
- `--worker-id`
- `--display-name`
- `--workdir`
- `--poll-interval`

示例：

```bash
dj-panel worker eval \
  --workspace llm-team \
  --worker-id eval-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-eval-worker \
  --poll-interval 5
```

### 7. 默认值解析规则

CLI 对 `workspace`、`user`、`base-url` 的解析有统一规则。

#### `base-url`

优先级：

1. 当前命令显式传入的 `--base-url`
2. 本地 config 中的 `base_url`
3. 默认值 `http://127.0.0.1:8000`

CLI 还会自动规范化这些写法：

- `localhost:8000` -> `http://localhost:8000`
- `http:localhost:8000` -> `http://localhost:8000`

#### `workspace`

优先级：

1. 当前命令显式传入的 `--workspace`
2. 本地 config 中的 `workspace`

如果仍为空，则报错。

#### `user`

优先级：

1. 当前命令显式传入的 `--user`、`--owner` 或 `--requested-by`
2. 本地 config 中的 `user`
3. 当前系统环境变量 `USER`

如果该命令要求用户身份但最终仍为空，则报错。

### 8. 输出形式

大部分命令支持 `--json`。

不加 `--json` 时：
- CLI 使用人类可读的表格或键值格式输出

加上 `--json` 时：
- 直接输出后端返回的 JSON 结果

适合脚本化场景：

```bash
dj-panel recipe list --workspace llm-team --json
```

### 9. 使用链路

典型 Data-Juicer 使用流程如下：

1. 启动 backend

```bash
dj-panel master --database-url postgresql+psycopg://... --migrate
```

2. 设置本地默认配置

```bash
dj-panel config set --workspace llm-team --user alice --base-url http://127.0.0.1:8000
```

3. 创建 workspace

```bash
dj-panel workspace create llm-team --owner alice --use
```

4. 导入 recipe

```bash
dj-panel recipe import ./config_lineage.yaml --name lineage_base --owner alice
```

5. 提交一次运行

```bash
dj-panel run submit --kind processing --spec ./process_spec.yaml --requested-by alice
```

6. 启动 worker 执行任务

```bash
dj-panel worker dj --worker-id dj-node-01 --workdir /tmp/dj-worker --poll-interval 5
```

7. 启动前端查看状态

```bash
dj-panel web --backend-url http://127.0.0.1:8000
```

典型 command-based training 使用流程如下：

1. 准备训练脚本和工作目录
2. 编写 `train_spec.yaml`
3. 提交训练任务

```bash
dj-panel run submit --workspace llm-team --kind training --spec ./train_spec.yaml --requested-by alice
```

4. 启动 training worker

```bash
dj-panel worker train --workspace llm-team --worker-id train-node-01 --workdir /tmp/dj-train-worker --poll-interval 5
```

5. 通过 task artifacts 中的日志文件观察训练输出

### 10. 当前边界

当前已覆盖：
- backend 启动
- web 开发服务启动
- workspace 管理
- recipe 导入与版本发布
- run submission 创建
- Data-Juicer worker 执行
- command-based training worker 执行
- command-based evaluation worker 执行

当前 CLI 还没有覆盖得很完整的内容：
- 更丰富的 run submission 查询与管理命令
- 手动 task 运维命令
- lineage 数据查询命令
- training/evaluation template 管理
- 结构化训练参数管理

---

## English

### 1. CLI Overview

`dj-panel` is the unified command-line entry point for the current backend project.
It currently covers six layers:

1. Startup layer: run the backend server and web development server
2. Local defaults layer: persist default `workspace`, `user`, and `base-url`
3. Collaboration layer: manage workspaces and members
4. Recipe layer: import, inspect, and publish Data-Juicer recipes
5. Submission layer: create a run submission from a recipe version
6. Worker execution layer: run Data-Juicer, training, or evaluation workers that claim and execute tasks

The current command tree is:

```text
dj-panel
├── master
├── web
├── config
│   ├── set
│   └── show
├── workspace
│   ├── create
│   ├── list
│   └── members
│       ├── add
│       └── list
├── recipe
│   ├── import
│   ├── list
│   ├── show
│   └── publish
├── run
│   ├── submit
│   ├── list
│   ├── show
│   ├── resume
│   ├── cancel
│   └── logs
└── worker
    ├── dj
    ├── train
    └── eval
```

### 2. Top-Level Commands

#### `dj-panel master`

Purpose:
- Start the DJ Panel backend FastAPI server
- Optionally run Alembic migrations before startup
- Optionally enable `uvicorn --reload` for local development

Common arguments:
- `--host`: bind address, default `127.0.0.1`
- `--port`: server port, default `8000`
- `--database-url`: database connection string; exported as `DATABASE_URL`
- `--migrate`: run `alembic upgrade head` before startup
- `--reload`: enable hot reload for development

Currently supported:
- PostgreSQL
- SQLite

Example:

```bash
dj-panel master --database-url postgresql+psycopg://user:pass@localhost:5432/dj_panel --migrate
```

SQLite example:

```bash
dj-panel master --database-url sqlite:///./dj_panel.db --migrate
```

#### `dj-panel web`

Purpose:
- Start the `dj-panel-web` frontend development server
- Inject the backend URL into the frontend through environment variables
- Optionally install frontend dependencies before startup

Common arguments:
- `--backend-url`: backend origin used by the frontend
- `--host`: frontend dev server bind address, default `127.0.0.1`
- `--port`: frontend dev server port, default `1337`
- `--web-dir`: frontend project directory; defaults to auto-detected `dj-panel-web`
- `--npm-bin`: npm executable name, default `npm`
- `--install-deps`: run `npm install` before startup
- `--open`: open a browser window automatically

Example:

```bash
dj-panel web --backend-url http://127.0.0.1:8000 --install-deps
```

#### `dj-panel config`

Purpose:
- Manage local CLI defaults
- Avoid repeating `--workspace`, `--user`, and `--base-url` on every command

Local config path:

```text
~/.config/dj-panel/config.json
```

##### `dj-panel config set`

Purpose:
- Set the default `workspace`
- Set the default `user`
- Set the default `base-url`

Common arguments:
- `--workspace`
- `--user`
- `--base-url`
- `--json`

Example:

```bash
dj-panel config set --workspace llm-team --user alice --base-url http://127.0.0.1:8000
```

##### `dj-panel config show`

Purpose:
- Show the current local CLI defaults

Example:

```bash
dj-panel config show
```

### 3. Workspace Layer

#### `dj-panel workspace create`

Purpose:
- Create a workspace
- Optionally store it as the local default workspace immediately

Common arguments:
- `slug`: unique workspace identifier
- `--name`: display name, defaults to `slug`
- `--description`
- `--owner`
- `--use`: persist the workspace into local config
- `--base-url`
- `--json`

Example:

```bash
dj-panel workspace create llm-team --name "LLM Team" --owner alice --use
```

#### `dj-panel workspace list`

Purpose:
- List workspaces currently available on the backend

Example:

```bash
dj-panel workspace list
```

#### `dj-panel workspace members add`

Purpose:
- Add a member to a workspace or update that member's role

Common arguments:
- `--workspace`
- `--user`
- `--role`

Supported roles:
- `OWNER`
- `MAINTAINER`
- `MEMBER`
- `VIEWER`

Example:

```bash
dj-panel workspace members add --workspace llm-team --user bob --role MEMBER
```

#### `dj-panel workspace members list`

Purpose:
- List the members of a workspace

Example:

```bash
dj-panel workspace members list --workspace llm-team
```

### 4. Recipe Layer

This layer is centered on Data-Juicer recipe YAML files. In the current CLI,
a recipe is treated as the reusable processing definition managed by the platform.

#### `dj-panel recipe import`

Purpose:
- Create a new recipe from a local YAML file
- Bring a recipe into the platform for the first time

Common arguments:
- `file`: local YAML file path
- `--workspace`
- `--owner`
- `--name`: recipe name; defaults to YAML `project_name`, otherwise file stem
- `--description`
- `--command`: defaults to `dj-process --config recipe.yaml`
- `--timeout-seconds`
- `--extra-execution-spec`: JSON merged into `executionSpec`
- `--json`

The CLI automatically builds:
- `recipeBody`
- `scriptPath`
- `parameterSchema`
- `envTemplate`
- `executionSpec`
- `timeoutSeconds`

Example:

```bash
dj-panel recipe import ./config_lineage.yaml --workspace llm-team --name lineage_base --owner alice
```

#### `dj-panel recipe list`

Purpose:
- List recipes in a workspace

Example:

```bash
dj-panel recipe list --workspace llm-team
```

#### `dj-panel recipe show`

Purpose:
- Show the details of a recipe
- Supports lookup by `recipe id`
- Also supports lookup by `workspace + recipe name`

Lookup by id:

```bash
dj-panel recipe show --recipe-id <recipe-id>
```

Lookup by workspace and name:

```bash
dj-panel recipe show --workspace llm-team --recipe lineage_base
```

#### `dj-panel recipe publish`

Purpose:
- Publish a new version of an existing recipe
- Commonly used when the YAML changes and a new recipe version should be released

Common arguments:
- `file`
- `--workspace`
- `--recipe`: existing recipe name
- `--owner`
- `--description`
- `--command`
- `--timeout-seconds`
- `--extra-execution-spec`
- `--json`

Example:

```bash
dj-panel recipe publish ./config_lineage_v2.yaml --workspace llm-team --recipe lineage_base --owner alice
```

### 5. Submission Layer

#### `dj-panel run submit`

Purpose:
- Create a `run submission`
- It represents a user request for the platform to launch one processing, training, or evaluation run
- After creation, the backend expands the submission into a claimable task

Common arguments:
- `--workspace`
- `--kind`: supports `processing`, `training`, and `evaluation`
- `--requested-by`
- `--parameters`: a JSON string or path to a JSON file; currently retained for command-based `training` / `evaluation`
- `--spec`: YAML/JSON object or file path describing the processing/training/evaluation submission
- `--name`
- `--json`

Notes:
- When `--kind processing` is used:
  `--spec` is required
- When `--kind training` or `--kind evaluation` is used:
  `--spec` is required
- The first processing spec version uses DJ Panel's higher-level structure with:
  - `kind`
  - `name`
  - `requestedBy`
  - `process.dj_configs`
  - `process.extra_configs`
  - `process.env`
  - `process.timeoutSeconds`

Example:

```bash
dj-panel run submit \
  --workspace llm-team \
  --kind processing \
  --spec ./process_spec.yaml \
  --requested-by alice
```

Training example:

```bash
dj-panel run submit \
  --workspace llm-team \
  --kind training \
  --spec ./train_spec.yaml \
  --requested-by alice
```

Evaluation example:

```bash
dj-panel run submit \
  --workspace llm-team \
  --kind evaluation \
  --spec ./eval_spec.yaml \
  --requested-by alice
```

Minimal `train_spec.yaml` example:

```yaml
name: qwen2-sft-v1
command: python train.py --config train.yaml
workdir: /mnt/team-repos/llm-trainer
env:
  MLFLOW_TRACKING_URI: http://127.0.0.1:5000
  MLFLOW_EXPERIMENT_NAME: qwen2-sft
timeoutSeconds: 7200
inputs:
  - uri: /data/processed/train.jsonl
outputs:
  - uri: /data/models/qwen2-sft-v1
```

Minimal `process_spec.yaml` example:

```yaml
kind: processing
name: demo-process-run
requestedBy: alice
process:
  dj_configs:
    mode: workspace_recipe
    name: lineage_base
  extra_configs:
    dataset_path: /data/raw/train.jsonl
    export_path: /data/processed/train.jsonl
  env:
    OPENLINEAGE_URL: http://127.0.0.1:8000/api/v1/lineage
  timeoutSeconds: 7200
```

Processing currently also supports:
- `process.dj_configs.mode = workspace_recipe`
- `process.dj_configs.mode = local_file`

In `local_file` mode:
- the CLI parses the YAML locally
- embeds `recipeBody` in the submission payload
- the worker materializes panel-side `recipe.yaml` by merging `recipeBody`, submission `parameters`, and the platform-injected `work_dir`

#### `dj-panel run list`

Purpose:
- List run submissions in a workspace

#### `dj-panel run show`

Purpose:
- Show one run submission in detail

#### `dj-panel run resume`

Purpose:
- Resume a `FAILED` or `CANCELLED` run submission
- Keep the original `task_id`
- Let the next worker attempt reuse the same DJ `job_id/work_dir`

Current limits:
- Only `FAILED` / `CANCELLED` are supported
- No new task is created; the original task is reset to `PENDING`

Example:

```bash
dj-panel run resume c42b30c2-8a86-43c4-a97d-bff1849ce1e7
```

#### `dj-panel run cancel`

Purpose:
- Cancel a `PENDING` run submission
- Mark both the submission and its derived task as `CANCELLED`

Current limits:
- Only `PENDING` is supported
- Running workers are not interrupted by this command

Example:

```bash
dj-panel run cancel bf3ea467-5805-46cd-a4b1-07df88242b97
```

#### `dj-panel run logs`

Purpose:
- Reserved command

Current status:
- Not implemented yet
```

### 6. Worker Execution Layer

#### `dj-panel worker dj`

Purpose:
- Start a Data-Juicer worker
- Register the worker
- Send periodic heartbeats
- Claim tasks of type `dj_recipe`
- Merge submission parameters into the recipe and materialize a local `recipe.yaml`
- Run `dj-process`
- Register log file artifacts, other artifacts, and task transitions back to the backend

Common arguments:
- `--base-url`
- `--workspace`
- `--worker-id`
- `--display-name`
- `--workdir`
- `--dj-bin`
- `--poll-interval`

Key behavior:

1. Register the worker through the worker registration API
2. Send a heartbeat through the heartbeat API
3. Claim only tasks where `taskKind = dj_recipe`
4. Materialize the recipe at `<workdir>/tasks/<task_id>/recipe.yaml`
5. Execute a command like:

```bash
dj-process --config /.../tasks/<task_id>/recipe.yaml --job_id <task_id>
```

6. Use that same task directory as DJ's final `work_dir`
7. Write execution output to `<workdir>/tasks/<task_id>/run.log` and register it as a `LOG` artifact
8. Report the materialized recipe as a `CONFIG` artifact
9. Transition the task through `start`, `complete`, or `fail`

Single-shot mode:
- If `--poll-interval <= 0`, the worker claims at most once

Polling mode:
- If `--poll-interval > 0`, the worker loops continuously

Example:

```bash
dj-panel worker dj \
  --workspace llm-team \
  --worker-id dj-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /Users/dludora/Code/data-juicer \
  --dj-bin dj-process \
  --poll-interval 5
```

#### `dj-panel worker train`

Purpose:
- Start a command-based training worker
- Register the worker
- Send periodic heartbeats
- Claim tasks of type `training`
- Execute the task `command` directly in the declared `workdir`
- Register log file artifacts and task transitions back to the backend

Common arguments:
- `--base-url`
- `--workspace`
- `--worker-id`
- `--display-name`
- `--workdir`
- `--poll-interval`

Example:

```bash
dj-panel worker train \
  --workspace llm-team \
  --worker-id train-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-train-worker \
  --poll-interval 5
```

#### `dj-panel worker eval`

Purpose:
- Start a command-based evaluation worker
- Register the worker
- Send periodic heartbeats
- Claim tasks of type `evaluation`
- Execute the task `command` directly in the declared `workdir`
- Register log file artifacts and task transitions back to the backend

Common arguments:
- `--base-url`
- `--workspace`
- `--worker-id`
- `--display-name`
- `--workdir`
- `--poll-interval`

Example:

```bash
dj-panel worker eval \
  --workspace llm-team \
  --worker-id eval-node-01 \
  --base-url http://127.0.0.1:8000 \
  --workdir /tmp/dj-eval-worker \
  --poll-interval 5
```

### 7. Default Resolution Rules

The CLI uses a shared resolution strategy for `workspace`, `user`, and `base-url`.

#### `base-url`

Priority:

1. `--base-url` provided on the current command
2. `base_url` stored in local config
3. Default `http://127.0.0.1:8000`

The CLI also normalizes common shorthand input:

- `localhost:8000` -> `http://localhost:8000`
- `http:localhost:8000` -> `http://localhost:8000`

#### `workspace`

Priority:

1. `--workspace` provided on the current command
2. `workspace` stored in local config

If still empty, the command fails.

#### `user`

Priority:

1. `--user`, `--owner`, or `--requested-by` on the current command
2. `user` stored in local config
3. Current shell environment variable `USER`

If the command requires a user identity and none can be resolved, the command fails.

### 8. Output Formats

Most commands support `--json`.

Without `--json`:
- The CLI prints human-readable tables or key-value output

With `--json`:
- The CLI prints raw JSON returned by the backend

Useful for scripting:

```bash
dj-panel recipe list --workspace llm-team --json
```

### 9. Recommended Workflow

A typical Data-Juicer flow looks like this:

1. Start the backend

```bash
dj-panel master --database-url postgresql+psycopg://... --migrate
```

2. Set local defaults

```bash
dj-panel config set --workspace llm-team --user alice --base-url http://127.0.0.1:8000
```

3. Create a workspace

```bash
dj-panel workspace create llm-team --owner alice --use
```

4. Import a recipe

```bash
dj-panel recipe import ./config_lineage.yaml --name lineage_base --owner alice
```

5. Submit a run

```bash
dj-panel run submit --kind processing --spec ./process_spec.yaml --requested-by alice
```

6. Start a worker

```bash
dj-panel worker dj --worker-id dj-node-01 --workdir /tmp/dj-worker --poll-interval 5
```

7. Start the frontend

```bash
dj-panel web --backend-url http://127.0.0.1:8000
```

A typical command-based training flow looks like this:

1. Prepare the training script and working directory
2. Write `train_spec.yaml`
3. Submit the training task

```bash
dj-panel run submit --workspace llm-team --kind training --spec ./train_spec.yaml --requested-by alice
```

4. Start the training worker

```bash
dj-panel worker train --workspace llm-team --worker-id train-node-01 --workdir /tmp/dj-train-worker --poll-interval 5
```

5. Inspect training output through log file artifacts attached to the task attempt

### 10. Current Boundaries

The CLI already covers:
- backend startup
- web dev server startup
- workspace management
- recipe import and version publishing
- run submission creation, listing, show, resume, and pending-only cancel
- Data-Juicer worker execution
- command-based training worker execution
- command-based evaluation worker execution

The CLI does not yet fully cover:
- `run logs`
- manual task operations
- lineage query commands
- training/evaluation template management
- structured training parameter management
