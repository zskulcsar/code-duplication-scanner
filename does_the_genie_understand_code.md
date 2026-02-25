# Does the Genie understand the code?
A couple of days ago, while walking the dog in the forest to take a break from my current project, I had the idea of using the Genie to check for code duplication. Checking for duplicated code is not trivial. Simple text matching and similar lexical analysis are not very useful, because what matters is not how the code looks, but what it does.

While working with the Genie on the project I took a break from, I created a /prompt that checks staged files via `git diff --cached` and asks the Genie to summarize the changes. Once I'm happy with the summary, it gets added to the commit message and we're good. This prompt came from the observation that Codex is fairly good at summarizing changes made.

Anyway, while walking in the forest, a question emerged: can we use an LLM to summarize pieces of code and run a Levenshtein-ratio cross-check across the codebase for similar summaries?

The hypothesis is that the LLM provides a logical summary, so we can use it to find meaningful code-duplication candidates.

On Friday morning, I jumped into the console and prompted the Genie to generate the code for this. You can find the result at (zskulcsar/code-duplication-scanner).

In a nutshell: 
- read the python sources pointed by the `--path` argument;
- read the Python sources specified by the `--path` argument;
- use `python.ast` to slurp up the code, remove any comment lines resulting only in a normalized code;
- call the LLM specified by the `--provider-url` and `--model` arguments to generate the "intent" from the normalized code (*this is important here: we don't want the LLM to use the documentation as hints. We want the pure code lines to be used for intent generation*)
- we do this for all classes, methods, and functions.
- finally, we persist the result in a simple SQLite database into two tables:
  - *runs* - metadata about the run, such as model used, path of sources, scope, things like that
  - *records* - data about what was processed (what kind of code, what file, signature, the raw and normalized code and the intent, some other things and of course the runs.id so that these tables are somewhat following good database design)

At this point we have the data persisted in a database and we can generate some sort of report. For that, we read all data from the database identified by `--run-id`, then cross-check the results as follows:
- **simple md5 match** -> the code on the left is exactly the same as on the right; clearly this is duplicated;
- **Levenshtein ratio** comparison (threshold is passed as `--threshold`) -> if the **normalized code** on the left is over the threshold compared to the right, then likely it is a duplication;
- finally, the same **Levenshtein ratio** and threshold are used to **compare intent** on the left with intent on the right. *ie.: if the LLM gives us a similar summary to the piece of code, then likely we have a duplicate.*

Now, this is interesting in itself, and the code is fairly simple, so one can use this on any Python project. Playing with various models (`qwen3-coder`, `gpt-oss:20b`, `gpt-5.2-codex`, `slekrem/gpt-oss-claude-code-32k:20b`) indicates that the hypothesis was correct, although we still need someone to read through all of those candidates and identify the ones that are actually actionable.

Anyway, the thing works and gives another way to find duplicated logic in code.
For experienced engineers, this is obviously helpful; for everyone else: code duplication is the arch-enemy of maintainability. Once you have fought through a recurring bug caused by the same logic being implemented in multiple places, you realize how important this is.

## Great. End of story, end of post ... or is it?

'cause two days later, I had another question while walking the dog in the forest during a break from my current project (yes, there is a theme; and yes, get out there and think. great ideas come like that):

**what if we "obfuscate" the code and ask the LLM for a summary of the obfuscated code?**

What am I talking about, you might ask?

Let's assume we have this code in our codebase:
```python
@dataclass(frozen=True)
class _FileAnalyzeResult:
    file_path: str
    symbols: list[ExtractedSymbol]
    error: AnalyzerError | None
```
which is easy to create a summary of, but now transform this code as below:
```python
@dataclass(frozen=True)
class ar:
    ik: str
    sn: list[k]
    hx: c | None
```
and ask the LLM on this "obfuscated/stripped" code for a summary.

Obviously, this is way harder to summarize. We stripped our code of any meaningful information to serve as hints. Although technically it is the same and we should have zero problem running it, finding the meaning is way more challenging.
But there is a point here (again, the experienced knows this already): meaningful variable, function, and class names are extremely important in code, and anyone who writes like the second example shall burn in hell.

That aside, the question remains:
- Will the LLM provide a meaningful summary of code stripped of its hints?
- Will the LLM actually find the logical meaning of said code or is it just using the hints provided by the good naming to infer the logic?

So we have another question to test: **does the LLM understand code?** (the experienced should know by now why this is a really important question, for others: it is important to validate, otherwise how can anyone trust at any levels the code generated by the AI agent?) 

Anyway, let's get together with the Genie and write the code for this (aka. experiment within the experiment) as follows:
- make a copy of the code pointed by the `--path`
- slurp up the copy, parse it via `python.ast`
- rename anything we can (imports, class/function/method/variable names, any call arguments), but leave comments as is as well as string literals, except for arguments in those string literals.
- write everything back to the file where the code came from, as they appeared in the code.
- run the code-duplication scanner on the original and the obfuscated version, then observe the results.

**A note here:** *when generating the intent, the prompt includes only the signature and the body. Comments and imports are not passed to the LLM to act as hints.*

**Another note:** *If the replacements were done properly, we should end up with a codebase like the second example, and it should run without problems because it is technically the same code with meaningless names.*

It took us about 3-4 hours to get there, and I started running the experiments.

## The result

### An example for the code pair:
```python
class _FileAnalyzeResult:
    file_path: str
    symbols: list[ExtractedSymbol]
    error: AnalyzerError | None
```
vs.
```python
class ar:
    ik: str
    sn: list[k]
    hx: c | None
```
qwen3-coder:latest intent | gpt-oss:20b intent | slekrem/gpt-oss-claude-code-32k:20b | gpt-5.2-codex intent |
|-|-|-|-|
| The code defines a data class to store the results of a file analysis, including the file path, extracted symbols, and any error that occurred during analysis. | Represents a file‑analysis result, storing the file path, extracted symbols, and any error that occurred. | Defines a data container for a file‑analysis result, holding the file path, extracted symbols, and any error. | Defines a data container for file analysis results with a path, extracted symbols, and an optional error. |
| This code defines a class `ar` with three attributes: `ik` (a string), `sn` (a list of elements of type `k`), and `hx` (an optional element of type `c`). | It declares a class `ar` that holds a string, a list of `k` objects, and an optional `c` object. | Defines a class with typed fields: a string, a list of k, and an optional c. | Defines a class `ar` with annotated attributes `ik` (string), `sn` (list of `k`), and optional `hx` of type `c`. |

### another example for the pair:
```python
def iter_similarity_pairs(
    records: list[Record], threshold: float
) -> list[tuple[float, Record, Record]]:
    matches: list[tuple[float, Record, Record]] = []
    for i, left in enumerate(records):
        for right in records[i + 1 :]:
            score = Levenshtein.ratio(left.intent, right.intent)
            if score >= threshold:
                matches.append((score, left, right))
    return matches
```
vs.
```python
def km(po: list[ad], wb: float) -> list[tuple[float, ad, ad]]:
    lw: list[tuple[float, ad, ad]] = []
    for jr, kv in enumerate(po):
        for qk in po[jr + 1 :]:
            rf = xv.ratio(kv.jz, qk.jz)
            if rf >= wb:
                lw.append((rf, kv, qk))
    return lw
```
| qwen3-coder:latest intent | gpt-oss:20b intent | slekrem/gpt-oss-claude-code-32k:20b | gpt-5.2-codex intent |
|-|-|-|-|
| The function finds pairs of similar records based on a Levenshtein similarity threshold. | Finds and returns pairs of records whose intent strings are similar above a given threshold. | Finds and returns all pairs of records whose intent strings have a Levenshtein similarity score above the given threshold.| It computes Levenshtein similarity scores for all unique record pairs and returns those meeting a threshold. |
| The function finds pairs of elements from a list where their ratio meets or exceeds a threshold value, returning the ratios along with the paired elements. | Collects all pairs of items in po whose jz‑value ratio is at least wb, returning each pair together with that ratio. | Finds and returns every pair of items in the list whose ratio of `jz` values meets or exceeds the given threshold. | Computes all unique pairs from the list whose `jz` similarity ratio meets a threshold and returns them with their score. |

Not really surprising. In the end, these classes, methods, and functions are too simple to understand without naming context. Even a human can only tell after checking how these are used in the wider context of the codebase, which we don't provide for the LLM to infer intent from.

## I hear you, this is a valid challenge.

So let me give you this:
### [analyzer.py#def analyze_project\(project_root: Path, files: list\[Path\]\) -> ProjectIndex:](https://github.com/zskulcsar/code-duplication-scanner/blob/main/docs/post/analyze_project.py) vs. [analyzer.py#def es\(oy: Path, it: list\[Path\]\) -> aa:](https://github.com/zskulcsar/code-duplication-scanner/blob/main/docs/post/es.py)

qwen3-coder:latest intent | gpt-oss:20b intent | slekrem/gpt-oss-claude-code-32k:20b | gpt-5.2-codex intent |
|-|-|-|-|
| This function analyzes a Python project by parsing all source files to collect information about symbols, classes, attributes, and potential renames, returning a structured index of the project's symbolic content. | Collects symbol data from all project files, removes external names from rename candidates, and returns an index of classes, attributes, and dynamic attributes. | It parses a project’s Python files, collects symbol data, and returns a structured index of rename candidates, external symbols, class names, attributes, and dynamic attributes. | Parses and analyzes project source files to collect and return symbol sets for renaming and indexing. | 
| This function analyzes a list of files to extract and categorize different types of code elements (py, ig, ox, ow, la) while handling various read and parse errors. | Analyzes a list of Python files, collecting defined, imported, and other symbol names, and returns aggregated sets of these names. | It analyzes a list of files, extracts and categorizes identifiers into sets, and returns those sets as immutable collections. | It analyzes a list of Python files, collecting and filtering various identifier sets from their parsed ASTs, and returns them in a result object. |

and this
### [rewriter.py#class _Renamer\(ast.NodeTransformer\):](https://github.com/zskulcsar/code-duplication-scanner/blob/main/docs/post/renamer.py) vs. [rewriter.py#class av\(xr.NodeTransformer\):](https://github.com/zskulcsar/code-duplication-scanner/blob/main/docs/post/av.py)

| qwen3-coder:latest intent | gpt-oss:20b intent | slekrem/gpt-oss-claude-code-32k:20b | gpt-5.2-codex intent |
|-|-|-|-|
| This code defines a Python AST visitor class `_Renamer` that systematically renames symbols (variables, attributes, functions, etc.) in Python code based on a provided mapping, while intelligently handling scope, ownership, and external references to avoid breaking functionality. | Transforms a Python AST to rename identifiers per a mapping, while tracking scopes, imports, and symbol ownership. | Renames identifiers in a Python AST according to a mapping, handling imports, scopes, and ownership rules. | Defines an AST transformer that renames project symbols and import aliases based on a mapping while tracking scope/ownership to avoid renaming external references.|
| This code defines a Python AST transformer class `av` that renames identifiers (variables, functions, classes, etc.) based on provided mapping and tracking rules, while also handling import statements and attribute access. | This code implements an AST transformer that renames variables, functions, imports, and attributes according to supplied mappings and scopes, effectively obfuscating or minifying the source code. | It rewrites a Python AST, renaming identifiers according to a mapping while tracking scope, usage, and preserving semantics. | Implements an AST transformer that renames identifiers/imports/attributes according to mappings while tracking scope and inferring origins to avoid unsafe renames. |


## And this is where I'm not exactly losing my shit, but I am extremely conflicted.
It seems that once LLMs had enough code to infer meaning, they did infer meaning, and that inferred meaning was spot on. And not just that. Even qwen3-coder, or gpt-oss did it. They are not exactly frontier models, and gpt-oss is not even a coding model.

## So the question: do LLMs understand code?
I don't know. I think we need more experiments on larger codebases, but it seems to me that these models can grasp deeper structural meaning beyond naming, which is the essence.

Ok - ok, you might say. In the case of `av` (aka `_Renamer`), the stripped code still has references to the `ast` module through argument types and method calls, but I challenge you to understand the stripped code.

### Side note

In hindsight, this is not surprising. To write or generate reasonable code (that is, code that does what it is meant to do) one must have an "understanding" of that code beyond the naming simply because naming is secondary to logic, and over the last few months we have seen that AI agents can generate reasonable code.

That said, I'm not stating the LLMs understand code in the traditional sense, but at least they can generate a textual representation for the purpose of the code, which seems to be good enough to work with.
