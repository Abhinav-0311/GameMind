param(
    [string]$ComposeFile = "docker-compose.yml",
    [string]$EnvFile = "",
    [string]$DatabaseUser = "postgres",
    [string]$SourceDatabase = "gamemind"
)

$ErrorActionPreference = "Stop"
$restoreDatabase = "gamemind_restore_verify"
$dumpPath = "/tmp/gamemind-restore-verify.dump"
$composeArgs = @("compose")
if ($EnvFile) {
    $composeArgs += @("--env-file", $EnvFile)
}
$composeArgs += @("-f", $ComposeFile)
$restoreCreated = $false

foreach ($identifier in @($DatabaseUser, $SourceDatabase, $restoreDatabase)) {
    if ($identifier -notmatch "^[a-zA-Z_][a-zA-Z0-9_]{0,62}$") {
        throw "Unsafe PostgreSQL identifier: $identifier"
    }
}

function Invoke-Compose {
    param([string[]]$Arguments)

    $output = & docker @composeArgs @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ($output -join [Environment]::NewLine)
    }
    return $output
}

try {
    $existing = Invoke-Compose @(
        "exec", "-T", "db", "psql", "-U", $DatabaseUser, "-d", "postgres",
        "-Atc", "SELECT 1 FROM pg_database WHERE datname='$restoreDatabase'"
    )
    if (($existing -join "").Trim() -eq "1") {
        throw "Refusing to continue because temporary database '$restoreDatabase' already exists."
    }

    Invoke-Compose @(
        "exec", "-T", "db", "pg_dump", "-U", $DatabaseUser, "-d", $SourceDatabase,
        "--format=custom", "--file=$dumpPath"
    ) | Out-Null
    Invoke-Compose @(
        "exec", "-T", "db", "createdb", "-U", $DatabaseUser, $restoreDatabase
    ) | Out-Null
    $restoreCreated = $true
    Invoke-Compose @(
        "exec", "-T", "db", "pg_restore", "-U", $DatabaseUser, "-d", $restoreDatabase,
        "--exit-on-error", "--no-owner", $dumpPath
    ) | Out-Null

    $sourceTables = Invoke-Compose @(
        "exec", "-T", "db", "psql", "-U", $DatabaseUser, "-d", $SourceDatabase,
        "-Atc", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    )
    $restoredTables = Invoke-Compose @(
        "exec", "-T", "db", "psql", "-U", $DatabaseUser, "-d", $restoreDatabase,
        "-Atc", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"
    )
    $sourceRevision = Invoke-Compose @(
        "exec", "-T", "db", "psql", "-U", $DatabaseUser, "-d", $SourceDatabase,
        "-Atc", "SELECT version_num FROM alembic_version"
    )
    $restoredRevision = Invoke-Compose @(
        "exec", "-T", "db", "psql", "-U", $DatabaseUser, "-d", $restoreDatabase,
        "-Atc", "SELECT version_num FROM alembic_version"
    )

    if (-not ($sourceTables -join "").Trim() -or -not ($restoredTables -join "").Trim()) {
        throw "Restore verification failed: table-count evidence is blank."
    }
    if (-not ($sourceRevision -join "").Trim() -or -not ($restoredRevision -join "").Trim()) {
        throw "Restore verification failed: Alembic revision evidence is blank."
    }
    if (($sourceTables -join "").Trim() -ne ($restoredTables -join "").Trim()) {
        throw "Restore verification failed: public table counts differ."
    }
    if (($sourceRevision -join "").Trim() -ne ($restoredRevision -join "").Trim()) {
        throw "Restore verification failed: Alembic revisions differ."
    }

    Write-Host "Backup restore verification passed."
    Write-Host "Public tables: $(($restoredTables -join '').Trim())"
    Write-Host "Alembic revision: $(($restoredRevision -join '').Trim())"
}
finally {
    if ($restoreCreated) {
        & docker @composeArgs exec -T db dropdb -U $DatabaseUser --force $restoreDatabase | Out-Null
    }
    & docker @composeArgs exec -T db rm -f $dumpPath | Out-Null
}
