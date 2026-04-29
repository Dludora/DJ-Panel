# DJ Panel CLI Reference

This document describes the current `dj-panel` CLI from the codebase as it exists today.
It focuses on command hierarchy, responsibilities at each layer, common workflows, and
how defaults are resolved.

---

## 中文

### 1. CLI 总览

`dj-panel` 是当前后端项目的统一命令行入口，主要覆盖六个层级：

1. 启动层：启动后端服务与 Web 开发服务
2. 本地配置层：保存默认的 `workspace`、`user`、`base-url`
3. 团队协作层：管理工作空间与成员
4. Recipe 管理层：导入、查看、发布 Data-Juicer recipe
5. 运行提交层：基于 recipe version 创建一次 run submission
6. Worker 执行层：启动 Data-Juicer worker，持续认领并执行任务

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
│   └── submit
└── worker
    └── dj
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

本地配置文件位置：

```text
~/.config/dj-panel/config.json
```

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
- 它表示“用户希望平台基于某个 recipe version 发起一次处理运行”
- 提交成功后，后端会基于 submission 展开可认领的 task

常见参数：
- `--workspace`
- `--recipe`：用 recipe 当前版本提交
- `--recipe-version-id`：直接指定版本
- `--requested-by`
- `--parameters`：JSON 字符串或 JSON 文件路径，会在 worker 物化 recipe 时合并到 `recipeBody`
- `--json`

注意：
- `--recipe` 和 `--recipe-version-id` 至少要提供一个
- 如果只提供 `--recipe`，CLI 会先查出该 recipe 的当前版本，再创建 submission

示例：

```bash
dj-panel run submit --workspace llm-team --recipe lineage_base --requested-by alice
```

带参数覆盖的示例：

```bash
dj-panel run submit --workspace llm-team --recipe lineage_base --parameters '{"dataset_path": "/data/raw/train.jsonl"}'
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
- 持续上报 task log、artifact、任务状态

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
dj-process --config /.../tasks/<task_id>/recipe.yaml
```

6. 把日志写入 `task_logs`
7. 把物化后的 recipe 作为 `CONFIG` artifact 上报
8. 根据执行结果调用 `start` / `complete` / `fail`

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
dj-panel run submit --recipe lineage_base --requested-by alice
```

6. 启动 worker 执行任务

```bash
dj-panel worker dj --worker-id dj-node-01 --workdir /tmp/dj-worker --poll-interval 5
```

7. 启动前端查看状态

```bash
dj-panel web --backend-url http://127.0.0.1:8000
```

### 10. 当前边界

当前已覆盖：
- backend 启动
- web 开发服务启动
- workspace 管理
- recipe 导入与版本发布
- run submission 创建
- Data-Juicer worker 执行

当前 CLI 还没有覆盖得很完整的内容：
- 更丰富的 run submission 查询与管理命令
- 手动 task 运维命令
- lineage 数据查询命令
- 训练、评测等非 DJ worker 类型

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
6. Worker execution layer: run a Data-Juicer worker that claims and executes tasks

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
│   └── submit
└── worker
    └── dj
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
- It represents a user request for the platform to launch one processing run from a recipe version
- After creation, the backend expands the submission into a claimable task

Common arguments:
- `--workspace`
- `--recipe`: submit using the recipe's current version
- `--recipe-version-id`: submit using a specific version directly
- `--requested-by`
- `--parameters`: a JSON string or path to a JSON file; merged into `recipeBody` when the worker materializes the recipe
- `--json`

Notes:
- At least one of `--recipe` or `--recipe-version-id` must be provided
- If only `--recipe` is provided, the CLI resolves the recipe's current version before creating the submission

Example:

```bash
dj-panel run submit --workspace llm-team --recipe lineage_base --requested-by alice
```

Example with parameter overrides:

```bash
dj-panel run submit --workspace llm-team --recipe lineage_base --parameters '{"dataset_path": "/data/raw/train.jsonl"}'
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
- Report task logs, artifacts, and task transitions back to the backend

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
dj-process --config /.../tasks/<task_id>/recipe.yaml
```

6. Stream logs into `task_logs`
7. Report the materialized recipe as a `CONFIG` artifact
8. Transition the task through `start`, `complete`, or `fail`

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
dj-panel run submit --recipe lineage_base --requested-by alice
```

6. Start a worker

```bash
dj-panel worker dj --worker-id dj-node-01 --workdir /tmp/dj-worker --poll-interval 5
```

7. Start the frontend

```bash
dj-panel web --backend-url http://127.0.0.1:8000
```

### 10. Current Boundaries

The CLI already covers:
- backend startup
- web dev server startup
- workspace management
- recipe import and version publishing
- run submission creation
- Data-Juicer worker execution

The CLI does not yet fully cover:
- richer run submission inspection and management commands
- manual task operations
- lineage query commands
- non-DJ worker types such as training or evaluation
