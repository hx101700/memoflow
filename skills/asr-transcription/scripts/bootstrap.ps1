#Requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$Workspace)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
# 固定使用当前PowerShell自带的摘要函数，避免继承其他版本的模块路径。
Import-Module (Join-Path $PSHOME 'Modules/Microsoft.PowerShell.Utility')

function Get-PlainDirectory {
    # 取得已有普通目录的绝对路径，确保首次写入不会经过目录联接。
    param([string]$Path)
    $directory = Get-Item -LiteralPath $Path -Force
    if (-not $directory.PSIsContainer) { throw "不是文件夹：$Path" }
    $current = $directory
    while ($null -ne $current) {
        if ($current.LinkType) { throw "运行时安装目录不支持符号链接或目录联接：$($current.FullName)" }
        $current = $current.Parent
    }
    return $directory.FullName
}

function Test-Inside {
    # 比较两个绝对目录是否相同或存在包含关系。
    param([string]$Path, [string]$Parent)
    return $Path.Equals($Parent, [StringComparison]::OrdinalIgnoreCase) -or
        $Path.StartsWith($Parent.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)
}

function Get-InstallRoot {
    # 校验工作目录与Skill边界，再准备本次私有安装目录。
    param([string]$WorkspacePath, [string]$SkillRoot)
    $workspaceDirectory = Get-PlainDirectory $WorkspacePath
    $skillDirectory = Get-PlainDirectory $SkillRoot
    $root = Join-Path $workspaceDirectory '.asr-transcription'
    if ((Test-Inside $workspaceDirectory $skillDirectory) -or (Test-Inside $skillDirectory $root)) {
        throw '请选择Skill资源目录之外的工作目录。'
    }
    foreach ($path in @($root, (Join-Path $root '.tools'), (Join-Path $root '.runtime'),
            (Join-Path $root '.runtime/runtime-downloads'), (Join-Path $root '.runtime/tmp'))) {
        if (Test-Path -LiteralPath $path) { $null = Get-PlainDirectory $path }
        else { $null = New-Item -ItemType Directory -Path $path }
    }
    return $root
}

function Get-RuntimeArchive {
    # 优先读取包内运行时，否则使用Windows curl下载并校验缓存。
    param([object]$Definition, [string]$Root)
    $fileName = ([Uri]$Definition.url).Segments[-1]
    $bundled = Join-Path (Split-Path -Parent $PSScriptRoot) ('assets/runtimes/' + $fileName)
    if (Test-Path -LiteralPath $bundled -PathType Leaf) {
        if ((Get-FileHash -LiteralPath $bundled -Algorithm SHA256).Hash -ne $Definition.sha256) {
            throw "安装包内运行时摘要不匹配，请重新获取完整安装包：$fileName"
        }
        return $bundled
    }
    $archive = Join-Path (Join-Path $Root '.runtime/runtime-downloads') $fileName
    $partial = $archive + '.part'
    foreach ($file in @($archive, $partial)) {
        if (Test-Path -LiteralPath $file) {
            $item = Get-Item -LiteralPath $file -Force
            if ($item.PSIsContainer -or $item.LinkType) { throw "下载缓存不是普通文件：$file" }
        }
    }
    if (Test-Path -LiteralPath $archive) {
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -eq $Definition.sha256) { return $archive }
        Remove-Item -LiteralPath $archive
    }
    $curl = Join-Path $env:SystemRoot 'System32/curl.exe'
    if (-not (Test-Path -LiteralPath $curl -PathType Leaf)) {
        throw '未找到Windows自带curl.exe，请更新Windows下载组件后再运行安装。'
    }
    [Console]::Error.WriteLine("正在下载 $fileName；完整包校验后才安装。")
    & $curl --fail --location --show-error --retry 2 --connect-timeout 30 --speed-limit 1 --speed-time 120 --continue-at - --output $partial $Definition.url
    if ($LASTEXITCODE -ne 0) { throw "运行时下载失败（curl $LASTEXITCODE），再次运行可续接：$partial" }
    if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash -ne $Definition.sha256) {
        Remove-Item -LiteralPath $partial
        throw "运行时摘要不匹配，已丢弃损坏文件：$fileName"
    }
    Move-Item -LiteralPath $partial -Destination $archive
    return $archive
}

function Install-PrivateRuntime {
    # 从已验证归档发布一个本地运行时，保留已有安装目录。
    param([string]$Name, [object]$Definition, [string]$Root)
    $destination = Join-Path (Join-Path $Root '.tools') $Name
    if (Test-Path -LiteralPath $destination) {
        $null = Get-PlainDirectory $destination
        return $destination
    }
    $archive = Get-RuntimeArchive $Definition $Root
    $temporaryRoot = Join-Path $Root '.runtime/tmp'
    $staging = Join-Path $temporaryRoot ('runtime-' + [Guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $staging
    try {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive, $staging)
        $source = if ($Definition.archive_root) { Join-Path $staging $Definition.archive_root } else { $staging }
        if (-not (Test-Path -LiteralPath (Join-Path $source ($Name + '.exe')) -PathType Leaf)) {
            throw "运行时归档缺少入口：$Name.exe"
        }
        Move-Item -LiteralPath $source -Destination $destination
    }
    finally {
        if (Test-Path -LiteralPath $staging) {
            $resolved = Get-PlainDirectory $staging
            if (-not (Test-Inside $resolved $temporaryRoot)) { throw '临时目录超出安装范围。' }
            Remove-Item -LiteralPath $resolved -Recurse -Force
        }
    }
    return $destination
}

function Initialize-WorkspaceRuntime {
    # 准备工作目录Python与Node，返回依赖安装使用的Python入口。
    param([string]$WorkspacePath)
    if (-not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw '请在Windows 10/11 x64的64位PowerShell中运行安装。'
    }
    $skillRoot = Split-Path -Parent $PSScriptRoot
    $root = Get-InstallRoot $WorkspacePath $skillRoot
    $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'runtimes.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $pythonDirectory = Install-PrivateRuntime 'python' $manifest.python $root
    $nodeDirectory = Install-PrivateRuntime 'node' $manifest.node $root
    $python = Join-Path $pythonDirectory 'python.exe'
    $node = Join-Path $nodeDirectory 'node.exe'
    if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $node -PathType Leaf) -or
            -not (Test-Path -LiteralPath (Join-Path $nodeDirectory 'node_modules/npm/bin/npm-cli.js') -PathType Leaf)) {
        throw '工作目录运行时不完整；已有目录已保留，请检查.tools/python和.tools/node。'
    }
    $pythonInfo = & $python -I -B -X utf8 -c "import ensurepip, tkinter, venv, sys; print(sys.version.split()[0]); print(tkinter.Tcl().eval('info patchlevel'))"
    if ($LASTEXITCODE -ne 0) { throw '本地Python或Tcl/Tk无法加载，尚未安装业务依赖。' }
    [Console]::Error.WriteLine("本地Python与Tcl/Tk：$($pythonInfo -join ' / ')")
    return $python
}

if ($MyInvocation.InvocationName -ne '.') {
    try { $python = Initialize-WorkspaceRuntime $Workspace }
    catch {
        @{ status = 'failed'; message = $_.Exception.Message } | ConvertTo-Json -Compress
        exit 1
    }
    & $python -E -S -B -X utf8 (Join-Path $PSScriptRoot 'asr.py') --workspace (Get-PlainDirectory $Workspace) bootstrap
    exit $LASTEXITCODE
}
