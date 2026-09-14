from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import subprocess
import json
import os
import sys


class BashInput(BaseModel):
    command: str
    timeout: Optional[int] = 30


class ExecutePythonInput(BaseModel):
    code: str
    timeout: Optional[int] = 60
    libraries: Optional[List[str]] = None


class CreateChartInput(BaseModel):
    code: str
    output_path: str = "/tmp/chart.png"
    format: str = "png"


class GeneratePDFInput(BaseModel):
    content: str
    output_path: str = "/tmp/report.pdf"
    title: str = "Report"


class AskQuestionInput(BaseModel):
    question: str
    options: Optional[List[str]] = None


class CreateCrmActivityInput(BaseModel):
    contactId: Optional[str] = None
    companyId: Optional[str] = None
    type: str
    body: str


class FinishRunInput(BaseModel):
    runId: str
    summary: str
    result: Optional[dict] = None


class InspectRunInput(BaseModel):
    runId: str


class PostSlackMessageInput(BaseModel):
    channel: str
    message: str


class QueryCRMInput(BaseModel):
    query: str


class ReadCRMRecordInput(BaseModel):
    recordId: str
    kind: str


class ReadFileInput(BaseModel):
    path: str


class TodoInput(BaseModel):
    action: str
    text: Optional[str] = None


class WebFetchInput(BaseModel):
    url: str


class WebSearchInput(BaseModel):
    query: str


class WriteFileInput(BaseModel):
    path: str
    content: str


class RunnerAgentTools:
    def ask_question(self, input_data: AskQuestionInput) -> dict:
        return {"question": input_data.question, "options": input_data.options or []}

    def bash(self, input_data: BashInput) -> dict:
        try:
            result = subprocess.run(
                input_data.command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=input_data.timeout or 30
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "success": result.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {input_data.timeout}s", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    def execute_python(self, input_data: ExecutePythonInput) -> dict:
        """Execute Python code for data analysis with common libraries pre-installed"""
        try:
            # Create a temporary Python file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                # Add common imports
                imports = [
                    "import pandas as pd",
                    "import numpy as np",
                    "import matplotlib",
                    "matplotlib.use('Agg')",
                    "import matplotlib.pyplot as plt",
                    "import seaborn as sns",
                    "import json",
                    "import sqlite3",
                    "from datetime import datetime, timedelta",
                    "from typing import Any, Dict, List",
                ]
                f.write("\n".join(imports) + "\n\n")
                f.write(input_data.code)
                temp_path = f.name

            try:
                result = subprocess.run(
                    [sys.executable, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=input_data.timeout or 60
                )
                return {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "success": result.returncode == 0
                }
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except subprocess.TimeoutExpired:
            return {"error": f"Python execution timed out after {input_data.timeout}s", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    def create_chart(self, input_data: CreateChartInput) -> dict:
        """Generate a chart using matplotlib/seaborn and save to file"""
        try:
            import tempfile
            output_path = input_data.output_path or "/tmp/chart.png"
            fmt = input_data.format or "png"
            if not output_path.endswith(('.png', '.jpg', '.svg', '.pdf')):
                output_path = "/tmp/chart.png"
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(f"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import json

{input_data.code}

plt.tight_layout()
plt.savefig('{output_path}', format='{fmt}', dpi=150, bbox_inches='tight')
plt.close()
print(f'Chart saved to {output_path}')
""")
                temp_path = f.name

            try:
                result = subprocess.run(
                    [sys.executable, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "output_path": output_path,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "success": result.returncode == 0
                }
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as e:
            return {"error": str(e), "success": False}

    def generate_pdf(self, input_data: GeneratePDFInput) -> dict:
        """Generate a PDF report using reportlab"""
        try:
            import tempfile
            output_path = input_data.output_path or "/tmp/report.pdf"
            title = input_data.title or "Report"
            content = input_data.content or ""
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(f"""
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

doc = SimpleDocTemplate('{output_path}', pagesize=A4)
styles = getSampleStyleSheet()
story = []

# Title
title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18, spaceAfter=20, alignment=TA_CENTER)
story.append(Paragraph('{title}', title_style))
story.append(Spacer(1, 20))

# Content
content_style = ParagraphStyle('CustomBody', parent=styles['Normal'], fontSize=11, spaceAfter=10)
for line in {json.dumps(content.split(chr(10)))}:
    if line.strip():
        story.append(Paragraph(line, content_style))
        story.append(Spacer(1, 6))

doc.build(story)
print(f'PDF saved to {output_path}')
""")
                temp_path = f.name

            try:
                result = subprocess.run(
                    [sys.executable, temp_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                return {
                    "output_path": output_path,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "success": result.returncode == 0
                }
            finally:
                try:
                    os.unlink(temp_path)
                except:
                    pass
        except Exception as e:
            return {"error": str(e), "success": False}

    def create_crm_activity(self, input_data: CreateCrmActivityInput) -> dict:
        return {"activityId": "activity_123"}

    def finish_run(self, input_data: FinishRunInput) -> dict:
        return {"finished": True, "runId": input_data.runId}

    def glob(self, pattern: str) -> dict:
        import glob
        return {"files": glob.glob(pattern, recursive=True)}

    def grep(self, pattern: str, path: Optional[str] = None) -> dict:
        import subprocess
        try:
            cmd = ["grep", "-r", pattern] + ([path] if path else ["."])
            result = subprocess.run(cmd, capture_output=True, text=True)
            return {"matches": result.stdout.splitlines()}
        except Exception as e:
            return {"error": str(e)}

    def inspect_run(self, input_data: InspectRunInput) -> dict:
        return {"runId": input_data.runId, "status": "COMPLETED"}

    def post_slack_message(self, input_data: PostSlackMessageInput) -> dict:
        return {"posted": True, "channel": input_data.channel}

    def query_crm(self, input_data: QueryCRMInput) -> dict:
        # Use Python's sqlite3 module
        import sqlite3
        try:
            db_path = "/home/suri/proj/crm/backend/test.db"
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute(input_data.query)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            conn.close()
            return {
                "rows": [dict(zip(cols, row)) for row in rows],
                "columns": cols,
                "success": True
            }
        except Exception as e:
            return {"error": str(e), "success": False}

    def read_crm_record(self, input_data: ReadCRMRecordInput) -> dict:
        return {"record": {"id": input_data.recordId, "kind": input_data.kind}}

    def read_file(self, input_data: ReadFileInput) -> dict:
        try:
            with open(input_data.path, 'r') as f:
                return {"content": f.read(), "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}

    def todo(self, input_data: TodoInput) -> dict:
        return {"todo": input_data.text or input_data.action}

    def web_fetch(self, input_data: WebFetchInput) -> dict:
        import urllib.request
        try:
            with urllib.request.urlopen(input_data.url) as response:
                return {"content": response.read().decode('utf-8'), "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}

    def web_search(self, input_data: WebSearchInput) -> dict:
        return {"results": [], "note": "Use web_fetch for actual URLs"}

    def write_file(self, input_data: WriteFileInput) -> dict:
        try:
            os.makedirs(os.path.dirname(input_data.path), exist_ok=True)
            with open(input_data.path, 'w') as f:
                f.write(input_data.content)
            return {"written": True, "path": input_data.path, "success": True}
        except Exception as e:
            return {"error": str(e), "success": False}