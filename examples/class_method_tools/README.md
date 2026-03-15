# Class Method Tools 教程

這個教程專門示範：**同樣都是 `@tool`，ToolAnything 現在可以同時支援 module-level function 與 class method**，而且 `@tool` 與 `@classmethod` 的兩種 decorator 順序都能正常註冊與執行。

> 下列步驟都在 repo 根目錄執行。

## 你會學到什麼

1. `@tool(...)` 在外層、`@classmethod` 在內層的寫法。
2. `@classmethod` 在外層、`@tool(...)` 在內層的寫法。
3. 這兩種寫法在 Python descriptor 模型下的差異。
4. ToolAnything 內部如何把這兩種寫法都整理成可用的 MCP tool。

## 範例檔案

- `examples/class_method_tools/demo.py`

執行：

```powershell
python examples/class_method_tools/demo.py
```

預期輸出會包含：

- 兩支已註冊工具：
  - `classmethod.outer_order`
  - `classmethod.inner_order`
- 直接呼叫 class method 的結果
- 透過 `registry.invoke_tool_async(...)` 呼叫工具的結果

## 寫法一：`@tool(...)` 在外層，`@classmethod` 在內層

```python
class OuterToolOrder:
    @tool(name="classmethod.outer_order", description="示範 @tool 在外、@classmethod 在內", registry=registry)
    @classmethod
    def greet(cls, name: str) -> str:
        return f"{cls.__name__} says hello to {name}"
```

### Python 層機制

Python 會先執行最內層的 `@classmethod`，把函數包成 `classmethod` descriptor；接著外層的 `@tool(...)` 收到的已經不是普通函數，而是一個 descriptor。

如果框架只會「立刻把收到的東西當 callable 註冊」，這種寫法通常會壞掉，因為 `classmethod` descriptor 本身不是最後要執行的 bound method。

### ToolAnything 內部怎麼處理

ToolAnything 會在 class body 階段先包一層 descriptor-aware wrapper，等 class 真正建立完成、Python 呼叫 `__set_name__()` 後，再回頭用 `getattr(OwnerClass, "greet")` 取到**已綁定 `cls` 的 class method** 來註冊。

這樣最後進 registry 的是可直接執行的 bound method，不是半成品 descriptor。

### 優點

- `@tool(...)` 放在最外層，閱讀時最醒目，對「先看 tool metadata」的人比較直覺。
- `name`、`description`、`tags`、`metadata` 都集中在最外層，文件感比較強。
- 對於想把「這是一支 tool」視為最高層語意的人，這個順序更容易掃讀。

### 缺點

- 純 Python 直覺上比較不容易立刻看出內部其實先形成了 `classmethod` descriptor。
- 若框架沒做 descriptor-aware 處理，這種寫法最容易失敗。
- 對沒碰過 descriptor 的讀者來說，魔法感會稍高。

## 寫法二：`@classmethod` 在外層，`@tool(...)` 在內層

```python
class OuterClassMethodOrder:
    @classmethod
    @tool(name="classmethod.inner_order", description="示範 @classmethod 在外、@tool 在內", registry=registry)
    def greet(cls, name: str) -> str:
        return f"{cls.__name__} says hello to {name}"
```

### Python 層機制

Python 會先執行最內層的 `@tool(...)`，此時它拿到的是原始函數；之後外層 `@classmethod` 再把這個結果包成 class method。

如果框架在 `@tool(...)` 當下就直接註冊原始函數，執行時通常會缺 `cls`。因為真正可用的 callable 要等到外層 `@classmethod` 完成、class 建立後，才會變成綁定好的 class method。

### ToolAnything 內部怎麼處理

ToolAnything 會先保留 `@tool(...)` 回傳的 wrapper，並在 class body 內掛一個暫時 hook。等 class 建立完成後，hook 會拿到 owner class，再把 `getattr(OwnerClass, "greet")` 的結果註冊進 registry。

因此即使 `@tool(...)` 寫在內層，實際註冊時仍然拿得到最終的 bound class method。

### 優點

- 對熟悉 Python decorator 疊法的人來說，語意比較貼近「先做 tool 包裝，再宣告這是 class method」。
- `Greeter.__dict__["greet"]` 最終仍是標準 `classmethod` 物件，和一般 Python 類別寫法一致。
- 如果你在乎「先保留函數包裝，再交給 `@classmethod` 統一處理」，這個順序較符合直覺。

### 缺點

- `@tool(...)` 不是最外層，掃碼時 metadata 比較不顯眼。
- 對第一次接觸的人，容易誤以為 `@tool(...)` 在 class 定義當下就完成註冊，其實真正註冊仍然要等 class 建立完成。

## 兩種寫法的共同點

- 對 ToolAnything 使用者而言，兩者都會得到：
  - 正確的 tool 名稱
  - 正確的 schema
  - 可直接透過 registry / MCP 呼叫的 bound class method
- 兩者都不需要你手動傳 `cls`
- 兩者都能保留一般 `Greeter.greet("Ada")` 的 class method 使用方式

## 建議怎麼選

- 想強調「這是一支工具」：優先用 `@tool(...)` 在外層。
- 想維持較典型的 Python method 宣告閱讀順序：用 `@classmethod` 在外層。
- 如果你的團隊沒有既有偏好，建議選一種後統一，不要在同一模組混用太多風格。

## 為什麼現在能支援兩種寫法

這不是因為 `classmethod` 比較特別，而是因為 ToolAnything 現在會把 decorator 寫法拆成兩個階段處理：

1. class body 階段：先保留 wrapper / descriptor 資訊，不急著把半成品直接註冊。
2. class 建立完成後：再取出最終可執行的 bound callable 註冊成 tool。

這個設計對應到 Python 官方文件裡的兩個重點：

- `classmethod` 會在屬性存取時產生綁定到 class 的 method
- descriptor 可以透過 `__set_name__()` 在 class 建立完成後拿到 owner 與 attribute name

參考資料：

- Python Built-in Functions: [`classmethod`](https://docs.python.org/3/library/functions.html#classmethod)
- Python Descriptor HowTo Guide: [`__set_name__()` 與 method binding](https://docs.python.org/3/howto/descriptor.html)
