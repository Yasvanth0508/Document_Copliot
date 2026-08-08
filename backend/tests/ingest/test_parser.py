from ingest.parser import parse_html_to_markdown


def test_parse_html_removes_scripts_and_styles():
    html = """
    <html>
        <head>
            <style>body { color: red; }</style>
            <script>alert('xss');</script>
        </head>
        <body>
            <h1>ITEM 1. BUSINESS</h1>
            <p>Apple designs consumer electronics.</p>
        </body>
    </html>
    """
    markdown = parse_html_to_markdown(html)
    assert "color: red" not in markdown
    assert "alert" not in markdown
    assert "# ITEM 1. BUSINESS" in markdown
    assert "Apple designs consumer electronics." in markdown


def test_parse_html_removes_hidden_xbrl():
    html = """
    <div>
        <span style="display:none">Hidden XBRL Tag</span>
        <p>Visible Financial Sentence.</p>
    </div>
    """
    markdown = parse_html_to_markdown(html)
    assert "Hidden XBRL Tag" not in markdown
    assert "Visible Financial Sentence." in markdown


def test_parse_html_converts_table():
    html = """
    <table>
        <tr><th>Segment</th><th>2024 Revenue</th></tr>
        <tr><td>iPhone</td><td>$201,183</td></tr>
        <tr><td>Services</td><td>$96,169</td></tr>
    </table>
    """
    markdown = parse_html_to_markdown(html)
    assert "| Segment | 2024 Revenue |" in markdown
    assert "| --- | --- |" in markdown
    assert "| iPhone | $201,183 |" in markdown
    assert "| Services | $96,169 |" in markdown


def test_parse_html_detects_item_headers():
    html = """
    <div>
        <p>ITEM 1A. RISK FACTORS</p>
        <p>Global economic conditions could adversely affect our business.</p>
        <p>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</p>
        <p>Revenue increased 8% year over year.</p>
    </div>
    """
    markdown = parse_html_to_markdown(html)
    assert "# ITEM 1A. RISK FACTORS" in markdown
    assert "# ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS" in markdown
