import io
import json
import re
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.llm import get_llm_response, FAST_MODEL, SMART_MODEL


class DataAnalystAgent:
    """
    LLM-driven data analyst agent.
    analyze() returns (fig, answer_text, plan) so the UI can
    offer chart-type overrides, color controls, and re-renders
    without re-calling the LLM.
    """

    CHART_TYPES = ["bar", "line", "pie", "scatter", "histogram", "box", "area"]

    COLOR_PALETTES = {
        "Default":    px.colors.qualitative.Plotly,
        "Pastel":     px.colors.qualitative.Pastel,
        "Bold":       px.colors.qualitative.Bold,
        "Vivid":      px.colors.qualitative.Vivid,
        "Ocean":      px.colors.sequential.Blues,
        "Sunset":     px.colors.sequential.Oranges,
        "Earth":      px.colors.sequential.Greens,
        "Monochrome": px.colors.sequential.Greys,
    }

    def __init__(self):
        self.df      = None
        self.schema  = None
        self.sources = {}  # name -> df for multi-file support

    # =========================================================
    # 1. LOAD + CLEAN  (CSV, XLSX, multi-sheet, multi-file)
    # =========================================================

    @staticmethod
    def read_file(uploaded_file):
        name = uploaded_file.name.lower()
        if name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            return {'Sheet1': df}
        elif name.endswith(('.xlsx', '.xls')):
            sheets = pd.read_excel(uploaded_file, sheet_name=None, engine='openpyxl')
            return sheets
        else:
            raise ValueError(f'Unsupported file type: {uploaded_file.name}')

    def load_dataframe(self, df: pd.DataFrame, source_name: str = 'Dataset'):

        # Auto-detect real header row
        header_row = None
        for i, row in df.iterrows():
            vals = row.dropna().astype(str).tolist()
            real = [v for v in vals if v.strip().lower() not in ("none", "nan", "")]
            if len(real) >= max(2, len(df.columns) // 2):
                header_row = i
                break

        if header_row is not None and header_row > 0:
            df.columns = df.iloc[header_row].astype(str).str.strip().values
            df = df.iloc[header_row + 1:].reset_index(drop=True)

        df = df.loc[:, ~df.columns.str.contains(r"^Unnamed|^nan$", case=False, regex=True)]
        df.columns = df.columns.str.strip()
        df = df.dropna(how="all").reset_index(drop=True)

        # % strings → float
        for col in df.columns:
            if df[col].dtype == "object":
                s = df[col].dropna().astype(str)
                if s.str.strip().str.endswith("%").any():
                    df[col] = pd.to_numeric(
                        df[col].astype(str).str.replace("%", "", regex=False).str.strip(),
                        errors="coerce"
                    )

        # numeric coercion
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = pd.to_numeric(df[col], errors="ignore")

        # datetime coercion
        for col in df.columns:
            try:
                if df[col].dtype == "object":
                    df[col] = pd.to_datetime(df[col], errors="raise", dayfirst=True)
            except Exception:
                pass

        self.df                  = df
        self.schema              = self._categorize_columns(df)
        self.sources[source_name] = df

    def load_source(self, name: str):
        if name not in self.sources:
            raise ValueError(f'Source not loaded: {name}')
        self.df     = self.sources[name]
        self.schema = self._categorize_columns(self.df)

    def get_data_summary(self) -> dict:
        df = self.df
        summary = {'rows': len(df), 'columns': len(df.columns), 'column_details': []}
        for col in df.columns:
            null_count = int(df[col].isna().sum())
            null_pct   = round(null_count / len(df) * 100, 1)
            unique     = int(df[col].nunique())
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                dtype = 'date'
                extra = f'{df[col].min().date()} to {df[col].max().date()}'
            elif pd.api.types.is_numeric_dtype(df[col]):
                dtype = 'numeric'
                extra = f'min {df[col].min():.2g} / max {df[col].max():.2g} / mean {df[col].mean():.2g}'
            else:
                dtype = 'text'
                top   = df[col].value_counts().index[0] if unique > 0 else '-'
                extra = f'top: {top!r} / {unique} unique values'
            summary['column_details'].append({
                'column': col, 'type': dtype,
                'nulls': null_count, 'null_pct': null_pct,
                'unique': unique, 'detail': extra,
            })
        return summary

    # =========================================================
    # 2. SCHEMA
    # =========================================================
    def _categorize_columns(self, df: pd.DataFrame) -> dict:
        numeric, categorical, date_cols = [], [], []
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                date_cols.append(col)
            elif pd.api.types.is_numeric_dtype(df[col]):
                numeric.append(col)
            else:
                categorical.append(col)
        return {
            "numeric":     numeric,
            "categorical": categorical,
            "date":        date_cols,
            "all":         list(df.columns),
        }

    # =========================================================
    # 3. LLM PLAN
    # =========================================================
    def _get_plan(self, question: str) -> dict:

        schema_info = {
            "numeric_columns":     self.schema["numeric"],
            "categorical_columns": self.schema["categorical"],
            "date_columns":        self.schema["date"],
        }
        sample = self.df.head(3).to_dict(orient="records")

        system = (
            "You are an expert data analyst planner. "
            "Return ONLY a valid JSON object. "
            "No markdown, no code fences, no explanation, no extra text whatsoever."
        )

        prompt = f"""
User question: "{question}"

Schema: {json.dumps(schema_info)}
Sample (3 rows): {json.dumps(sample, default=str)}

Pick MODE:
"lookup"    = user wants to SEE rows (which/list/find/show/who/where)
"aggregate" = user wants computed summary (average/total/sum/max/min/count per/how many per)
"explore"   = user wants pattern/distribution/trend/correlation/spread
"hybrid"    = BOTH filter rows AND summarise them

CHART RULES — follow exactly:
- "trend over time" / "month by month" / "over the year" → chart="line", x_col=date_col, groupby=date_col, agg_func="sum"
- "cumulative" / "growth over time"                      → chart="area", x_col=date_col
- "share" / "proportion" / "percentage of" / "breakdown" → chart="pie"
- "distribution" / "histogram"                           → chart="histogram", x_col=the numeric col
- "spread" / "range" / "box" / "outlier" / "across categories" → chart="box", x_col=categorical_col, y_col=numeric_col
- "relationship" / "correlation" / "vs"                  → chart="scatter"
- everything else                                        → chart="bar"

TREND/LINE SPECIAL RULE:
If chart is "line" or "area" and a date column exists:
  - Set groupby = date column name
  - Set agg_func = "sum" (or "mean" if question asks for average)
  - Set agg_col = the numeric column to aggregate
  - Set x_col = date column name
  - Set y_col = the numeric column to aggregate

HISTOGRAM SPECIAL RULE:
If chart is "histogram":
  - x_col MUST be the numeric column to distribute
  - groupby, agg_col, agg_func must all be null

BOX SPECIAL RULE:
If chart is "box":
  - x_col = categorical column (grouping)
  - y_col = numeric column (values)
  - groupby/agg_col/agg_func = null

Return ONLY this JSON:
{{
  "mode":      "<lookup|aggregate|explore|hybrid>",
  "filter":    <pandas query string or null>,
  "groupby":   <column name or null>,
  "agg_col":   <numeric column or null>,
  "agg_func":  <"mean"|"sum"|"max"|"min"|"count"|null>,
  "chart":     "<bar|line|pie|scatter|histogram|box|area>",
  "x_col":     <column name or null>,
  "y_col":     <column name or null>,
  "color_col": <column name or null>,
  "title":     "<short chart title>"
}}

Rules:
- ONLY use column names that exist in schema.
- Column names with spaces need backticks in filter: `Days Required` < 25
- color_col = null unless genuinely useful
- For pie: x_col = categorical grouping col, y_col = numeric value col
"""

        raw = get_llm_response(prompt=prompt, system_message=system, temperature=0.0, model=FAST_MODEL)
        cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()

        if not cleaned:
            raise ValueError(f"LLM returned empty response for: '{question}'")

        json_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)

        plan = json.loads(cleaned)

        # Sanitize column names
        all_cols = self.schema["all"]

        def valid(c):
            return c if (c and c in all_cols) else None

        plan["groupby"]   = valid(plan.get("groupby"))
        plan["agg_col"]   = valid(plan.get("agg_col"))
        plan["x_col"]     = valid(plan.get("x_col"))
        plan["y_col"]     = valid(plan.get("y_col"))
        plan["color_col"] = valid(plan.get("color_col"))

        if plan.get("agg_func") not in ("mean", "sum", "max", "min", "count"):
            plan["agg_func"] = None

        if plan.get("chart") not in self.CHART_TYPES:
            plan["chart"] = "bar"

        if plan.get("mode") not in ("lookup", "aggregate", "explore", "hybrid"):
            plan["mode"] = "lookup"

        return plan

    # =========================================================
    # 4. EXECUTE PLAN
    #    chart_override : force a specific chart type (from UI)
    #    palette        : colour palette name (from UI)
    #    single_color   : hex colour for single-colour charts
    # =========================================================
    def _execute_plan(
        self,
        plan:          dict,
        chart_override: str  = None,
        palette:        str  = "Default",
        single_color:   str  = None,
    ):
        df = self.df.copy()

        mode        = plan.get("mode", "lookup")
        filter_expr = plan.get("filter")
        groupby     = plan.get("groupby")
        agg_col     = plan.get("agg_col")
        agg_func    = plan.get("agg_func")
        chart       = chart_override or plan.get("chart", "bar")
        x_col       = plan.get("x_col")
        y_col       = plan.get("y_col")
        color_col   = plan.get("color_col")
        title       = plan.get("title", "")

        # Resolve colour settings
        color_seq   = self.COLOR_PALETTES.get(palette, self.COLOR_PALETTES["Default"])

        # ── 1. Filter ──────────────────────────────────────────────────────
        if filter_expr:
            try:
                df = df.query(filter_expr)
            except Exception as e:
                print(f"[DataAnalystAgent] Filter failed ({e!r}), skipping.")

        # ── 2. Empty guard ─────────────────────────────────────────────────
        if df.empty:
            fig = go.Figure()
            fig.update_layout(
                title=title or "No Results",
                annotations=[{
                    "text": "No records match the filter criteria.",
                    "xref": "paper", "yref": "paper",
                    "showarrow": False, "font": {"size": 16},
                    "x": 0.5, "y": 0.5,
                }],
            )
            return df, fig

        filtered_df = df.copy()

        # ── 3. Aggregate ───────────────────────────────────────────────────
        if groupby and agg_func:
            gb_col = groupby

            if chart in ("line", "area") and gb_col in self.schema["date"]:
                df[gb_col] = pd.to_datetime(df[gb_col])
                df = df.set_index(gb_col)
                target = agg_col or next(
                    (c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])), None
                )
                if target:
                    func = agg_func if agg_func in ("sum", "mean") else "sum"
                    df = getattr(df[target].resample("ME"), func)().reset_index()
                    agg_col = target
                x_col = gb_col
                y_col = agg_col

            elif agg_func == "count":
                df = (
                    df.groupby(gb_col, as_index=False)
                    .size()
                    .rename(columns={"size": "Count"})
                )
                x_col = x_col or gb_col
                y_col = "Count"

            elif agg_col:
                df = df.groupby(gb_col, as_index=False)[agg_col].agg(agg_func)
                x_col = x_col or gb_col
                y_col = y_col or agg_col

        # ── 4. Histogram: ensure numeric x_col ────────────────────────────
        if chart == "histogram":
            if not x_col or x_col not in df.columns or not pd.api.types.is_numeric_dtype(df[x_col]):
                num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
                x_col = num_cols[0] if num_cols else x_col

        # ── 5. Fallback x/y ────────────────────────────────────────────────
        if not x_col or x_col not in df.columns:
            non_dt = [c for c in df.columns if not pd.api.types.is_datetime64_any_dtype(df[c])]
            x_col = non_dt[0] if non_dt else df.columns[0]

        needs_y = chart in ("bar", "line", "scatter", "area", "box")
        if needs_y and (not y_col or y_col not in df.columns):
            num_cols = [
                c for c in df.columns
                if pd.api.types.is_numeric_dtype(df[c]) and c != x_col
            ]
            if num_cols:
                y_col = num_cols[0]
            else:
                count_df = df[x_col].value_counts().reset_index()
                count_df.columns = [x_col, "Count"]
                df    = count_df
                y_col = "Count"

        # ── 6. Render ──────────────────────────────────────────────────────
        kw = dict(title=title)

        # Apply colour: single_color overrides palette for non-categorical charts
        if single_color:
            kw["color_discrete_sequence"] = [single_color]

        if chart == "histogram":
            fig = px.histogram(
                df, x=x_col,
                color=color_col,
                color_discrete_sequence=color_seq if not single_color else [single_color],
                **kw
            )

        elif chart == "pie":
            names_col  = x_col or groupby
            values_col = y_col or agg_col
            cols = df.columns.tolist()
            if names_col in cols and values_col and values_col in cols:
                fig = px.pie(df, names=names_col, values=values_col,
                             color_discrete_sequence=color_seq, **kw)
            elif names_col in cols:
                counts = df[names_col].value_counts().reset_index()
                counts.columns = [names_col, "Count"]
                fig = px.pie(counts, names=names_col, values="Count",
                             color_discrete_sequence=color_seq, **kw)
            else:
                cat = self.schema["categorical"]
                c   = cat[0] if cat else df.columns[0]
                counts = df[c].value_counts().reset_index()
                counts.columns = [c, "Count"]
                fig = px.pie(counts, names=c, values="Count",
                             color_discrete_sequence=color_seq, **kw)

        elif chart == "scatter":
            fig = px.scatter(
                df, x=x_col, y=y_col,
                color=color_col,
                color_discrete_sequence=color_seq if color_col else None,
                **kw
            )
            if single_color and not color_col:
                fig.update_traces(marker_color=single_color)

        elif chart == "line":
            fig = px.line(
                df, x=x_col, y=y_col,
                color=color_col,
                color_discrete_sequence=color_seq if color_col else None,
                **kw
            )
            if single_color and not color_col:
                fig.update_traces(line_color=single_color)

        elif chart == "box":
            fig = px.box(
                df, x=x_col, y=y_col,
                color=color_col,
                color_discrete_sequence=color_seq,
                **kw
            )

        elif chart == "area":
            fig = px.area(
                df, x=x_col, y=y_col,
                color=color_col,
                color_discrete_sequence=color_seq if color_col else None,
                **kw
            )
            if single_color and not color_col:
                fig.update_traces(line_color=single_color, fillcolor=single_color)

        else:  # bar
            fig = px.bar(
                df, x=x_col, y=y_col,
                color=color_col,
                color_discrete_sequence=color_seq if color_col else [single_color or color_seq[0]],
                **kw
            )

        # ── 7. Axis labels ─────────────────────────────────────────────────
        if y_col == "Count":
            fig.update_layout(yaxis_title="Count")
        elif agg_func and y_col and chart not in ("pie", "histogram", "box"):
            fig.update_layout(yaxis_title=f"{agg_func.capitalize()} of {y_col}")

        # ── 8. Return ──────────────────────────────────────────────────────
        answer_df = filtered_df if mode in ("lookup", "hybrid") else df
        return answer_df, fig

    # =========================================================
    # 5. GENERATE ANSWER
    # =========================================================
    def _generate_answer(self, question: str, plan: dict, result_df: pd.DataFrame) -> str:

        mode = plan.get("mode", "lookup")

        if mode == "explore" and len(result_df) > 30:
            num_cols = [c for c in result_df.columns if pd.api.types.is_numeric_dtype(result_df[c])]
            if num_cols:
                stats = result_df[num_cols].describe().round(2).to_dict()
                result_sample   = [{"summary_stats": stats}]
                truncation_note = f"(stats from {len(result_df)} rows)"
            else:
                result_sample   = result_df.head(20).to_dict(orient="records")
                truncation_note = f"(first 20 of {len(result_df)} rows)"
        elif len(result_df) > 50:
            result_sample   = result_df.head(50).to_dict(orient="records")
            truncation_note = f"(first 50 of {len(result_df)} rows)"
        else:
            result_sample   = result_df.to_dict(orient="records")
            truncation_note = ""

        system = (
            "You are a data analyst giving a direct, precise answer. "
            "Use ONLY the data provided — cite real names and numbers. "
            "Write 1-2 paragraphs. "
            "Do NOT say 'based on the data', 'the results show', or mention charts. "
            "Answer directly as if explaining to a colleague."
        )

        mode_hints = {
            "lookup":    "List the specific matching records and state the total count.",
            "aggregate": "Summarise the computed values. Call out the highest and lowest.",
            "hybrid":    "State the total count AND list key items with values. Answer BOTH parts.",
            "explore":   "Describe the overall pattern, distribution, or trend from the stats.",
        }

        prompt = f"""
Question: "{question}"
Mode: {mode} — {mode_hints.get(mode, "")}

Filter: {plan.get("filter") or "none"}
Grouped by: {plan.get("groupby") or "none"}
Aggregation: {plan.get("agg_func") or "none"} of {plan.get("agg_col") or "n/a"}
Total records: {len(result_df)} {truncation_note}

Data:
{json.dumps(result_sample, indent=2, default=str)}

Write a clear 1-2 paragraph answer using specific numbers and names from the data.
"""

        return get_llm_response(prompt=prompt, system_message=system, temperature=0.2, model=SMART_MODEL).strip()

    # =========================================================
    # 6. PUBLIC API
    # =========================================================
    def analyze(self, question: str) -> tuple:
        """
        First-time analysis. Calls LLM to build plan.

        Returns:
            fig     (plotly Figure)
            answer  (str)
            plan    (dict)  ← returned so UI can re-render without re-calling LLM
        """
        if self.df is None:
            raise ValueError("No dataset loaded. Call load_dataframe() first.")

        plan           = self._get_plan(question)
        result_df, fig = self._execute_plan(plan)
        answer         = self._generate_answer(question, plan, result_df)

        return fig, answer, plan

    def rerender(
        self,
        plan:           dict,
        chart_override: str  = None,
        palette:        str  = "Default",
        single_color:   str  = None,
    ) -> go.Figure:
        """
        Re-render the chart without calling the LLM again.
        Called when user changes chart type, palette, or color in the UI.

        Returns:
            fig  (plotly Figure)
        """
        if self.df is None:
            raise ValueError("No dataset loaded.")

        _, fig = self._execute_plan(
            plan,
            chart_override=chart_override,
            palette=palette,
            single_color=single_color,
        )
        return fig