name: Update Trading Data

on:
  workflow_dispatch:
  schedule:
    - cron: '0 0 * * *'

jobs:
  update-data:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install yfinance

      - name: Run data update script
        run: |
          python update-data.py

      - name: Commit and push changes
        run: |
          git config --global user.name "GitHub Actions Bot"
          git config --global user.email "actions@github.com"
          git add data.json
          git commit -m "Auto-update market data.json [skip ci]" || exit 0
          git push
