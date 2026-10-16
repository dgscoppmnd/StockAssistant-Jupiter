param([string]$Container = 'proyecto_jupiter_api')
$ErrorActionPreference = 'Stop'
$automationTestRoot = Join-Path $PSScriptRoot '../tests'
foreach ($automationTestName in @('test_database_schema.py', 'test_operational_automation.py', 'test_ai_service.py', 'test_executive_rules.py')) {
    Write-Host "Running $automationTestName"
    Get-Content -Raw -Encoding UTF8 (Join-Path $automationTestRoot $automationTestName) |
        docker exec -i -e RUN_AUTOMATION_DB_TESTS=1 $Container python -
    if ($LASTEXITCODE -ne 0) { throw "Failed: $automationTestName" }
}
Get-Content -Raw -Encoding UTF8 (Join-Path $automationTestRoot 'test_sales_forecast_ai.py') |
    docker exec -i $Container python -c "import sys; scope={'__file__':'/app/tests/test_sales_forecast_ai.py','__name__':'forecast_test'}; exec(compile(sys.stdin.read(),scope['__file__'],'exec'),scope); tests=[v for k,v in scope.items() if k.startswith('test_') and callable(v)]; [fn() for fn in tests]; print(str(len(tests))+' forecast tests passed')"
if ($LASTEXITCODE -ne 0) { throw 'Failed: test_sales_forecast_ai.py' }
