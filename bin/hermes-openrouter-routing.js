#!/usr/bin/env node
/**
 * Hermes Task Router — CLI plugin installer
 *
 * Provider-agnostic smart task routing for Hermes.
 * Works with OpenRouter, Requesty, or any provider.
 *
 * Usage:
 *   hermes-openrouter-routing install     Install plugins
 *   hermes-openrouter-routing uninstall   Remove plugins, restore backups
 *   hermes-openrouter-routing status      Check installation status
 *   hermes-openrouter-routing --version   Print version
 *   hermes-openrouter-routing --help      Print usage
 */
'use strict';

const fs = require('fs');
const path = require('path');
const os = require('os');

const PKG_VERSION = '1.0.2';
const PKG_NAME = 'hermes-openrouter-routing';

// ── Color helpers ───────────────────────────────────────────────────
const COLORS = {
  reset: '\x1b[0m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  red: '\x1b[31m',
  cyan: '\x1b[36m',
  bold: '\x1b[1m',
};

function green(s) { return COLORS.green + s + COLORS.reset; }
function yellow(s) { return COLORS.yellow + s + COLORS.reset; }
function red(s) { return COLORS.red + s + COLORS.reset; }
function cyan(s) { return COLORS.cyan + s + COLORS.reset; }
function bold(s) { return COLORS.bold + s + COLORS.reset; }

// ── Path helpers ────────────────────────────────────────────────────
function pkgDir() {
  return path.resolve(__dirname, '..');
}

function hermesAgentDir() {
  return path.join(os.homedir(), '.hermes', 'hermes-agent');
}

function hermesPluginsDir() {
  return path.join(os.homedir(), '.hermes', 'plugins');
}

function backupPath(originalPath) {
  const now = new Date();
  const ts = now.getFullYear()
    + String(now.getMonth() + 1).padStart(2, '0')
    + String(now.getDate()).padStart(2, '0')
    + String(now.getHours()).padStart(2, '0')
    + String(now.getMinutes()).padStart(2, '0')
    + String(now.getSeconds()).padStart(2, '0');
  return originalPath + '.bak.' + ts;
}

// ── Install maps ────────────────────────────────────────────────────
// Each entry: { src, dst, isDir }
function getInstallEntries() {
  const base = pkgDir();
  const agent = hermesAgentDir();
  const userPlugins = hermesPluginsDir();

  return [
    {
      src: path.join(base, 'plugins', 'model-providers', 'openrouter', '__init__.py'),
      dst: path.join(agent, 'plugins', 'model-providers', 'openrouter', '__init__.py'),
    },
    {
      src: path.join(base, 'plugins', 'model-providers', 'openrouter', 'plugin.yaml'),
      dst: path.join(agent, 'plugins', 'model-providers', 'openrouter', 'plugin.yaml'),
    },
    {
      src: path.join(base, 'plugins', 'user', 'resolved-backend-model', '__init__.py'),
      dst: path.join(userPlugins, 'resolved-backend-model', '__init__.py'),
    },
    {
      src: path.join(base, 'plugins', 'user', 'resolved-backend-model', 'plugin.yaml'),
      dst: path.join(userPlugins, 'resolved-backend-model', 'plugin.yaml'),
    },
  ];
}

// ── Core install / uninstall / status ───────────────────────────────

function install() {
  const agentDir = hermesAgentDir();
  const userPluginsDir = hermesPluginsDir();

  // Verify Hermes directories exist
  if (!fs.existsSync(agentDir)) {
    console.error(red('✖ Hermes agent directory not found at: ' + agentDir));
    console.error(yellow('  Is Hermes installed? Run "hermes setup" first.'));
    process.exit(1);
  }

  const entries = getInstallEntries();
  let installed = 0;
  let skipped = 0;
  let backedUp = 0;

  console.log(bold('Installing task router plugins...\n'));

  for (const entry of entries) {
    // Ensure source exists
    if (!fs.existsSync(entry.src)) {
      console.warn(yellow('⚠  Source not found: ' + entry.src));
      skipped++;
      continue;
    }

    // Ensure destination parent directory exists
    const dstDir = path.dirname(entry.dst);
    if (!fs.existsSync(dstDir)) {
      fs.mkdirSync(dstDir, { recursive: true });
      console.log('  Created directory: ' + cyan(dstDir));
    }

    // Backup existing file
    if (fs.existsSync(entry.dst)) {
      const bak = backupPath(entry.dst);
      try {
        fs.copyFileSync(entry.dst, bak);
        backedUp++;
        console.log('  Backed up:       ' + yellow(path.basename(entry.dst) + ' → ' + path.basename(bak)));
      } catch (err) {
        console.error(red('✖ Failed to backup: ' + entry.dst + ' — ' + err.message));
      }
    }

    // Copy file
    try {
      fs.copyFileSync(entry.src, entry.dst);
      installed++;
      console.log('  ' + green('✔') + ' Installed:      ' + cyan(entry.dst));
    } catch (err) {
      console.error(red('✖ Failed to copy: ' + entry.src + ' → ' + entry.dst + ' — ' + err.message));
    }
  }

  console.log('\n' + green(bold('✓ Installation complete!')));
  console.log('  Files installed:   ' + installed);
  if (backedUp > 0) {
    console.log(yellow('  Files backed up:   ' + backedUp));
  }
  if (skipped > 0) {
    console.log(yellow('  Files skipped:     ' + skipped));
  }

  console.log('\n' + bold('Next steps:'));
  console.log('  1. Edit ' + cyan('~/.hermes/config.yaml'));
  console.log('  2. Add the following configuration:');
  console.log('');
  console.log('     ' + bold('openrouter:'));
  console.log('       ' + bold('routing:'));
  console.log('         enabled: true');
  console.log('         simple_model: "nvidia/nemotron-3-super-120b-a12b:free"');
  console.log('         complex_model: "deepseek/deepseek-v4-pro"');
  console.log('         default_model: "nvidia/nemotron-3-super-120b-a12b"');
  console.log('         router_model: "nvidia/nemotron-3-super-120b-a12b:free"');
  console.log('     ' + bold('extra_body:'));
  console.log('       ' + bold('requesty:'));
  console.log('         auto_cache: true');
  console.log('');
  console.log('  3. Make sure ' + cyan('OPENROUTER_API_KEY') + ' is set in ' + cyan('~/.hermes/.env'));
  console.log('     or in your environment variables.');
  console.log('');
  console.log('  4. Restart Hermes.');
}

function uninstall() {
  const agentDir = hermesAgentDir();
  const userPluginsDir = hermesPluginsDir();

  const entries = getInstallEntries();
  let removed = 0;
  let restored = 0;

  console.log(bold('Removing task router plugins...\n'));

  for (const entry of entries) {
    // Remove the installed file
    if (fs.existsSync(entry.dst)) {
      try {
        fs.unlinkSync(entry.dst);
        removed++;
        console.log('  ' + green('✔') + ' Removed:        ' + cyan(entry.dst));
      } catch (err) {
        console.error(red('✖ Failed to remove: ' + entry.dst + ' — ' + err.message));
      }
    } else {
      console.log('  Not installed:  ' + entry.dst);
    }

    // Look for backups to restore
    const dstDir = path.dirname(entry.dst);
    const baseName = path.basename(entry.dst);
    let backups;
    try {
      backups = fs.readdirSync(dstDir)
        .filter(f => f.startsWith(baseName + '.bak.'))
        .sort()
        .reverse();
    } catch (e) {
      backups = [];
    }

    if (backups.length > 0) {
      const latestBackup = path.join(dstDir, backups[0]);
      try {
        fs.copyFileSync(latestBackup, entry.dst);
        restored++;
        console.log('  ' + green('↩') + ' Restored from: ' + yellow(path.basename(latestBackup)));
      } catch (err) {
        console.error(red('✖ Failed to restore: ' + latestBackup + ' — ' + err.message));
      }
    }
  }

  // Clean up empty directories
  const dirsToClean = [
    path.join(agentDir, 'plugins', 'model-providers', 'openrouter'),
    path.join(userPluginsDir, 'resolved-backend-model'),
  ];
  for (const dir of dirsToClean) {
    if (fs.existsSync(dir)) {
      try {
        const remaining = fs.readdirSync(dir);
        if (remaining.length === 0) {
          fs.rmdirSync(dir);
          console.log('  Removed empty:  ' + cyan(dir));
        }
      } catch (e) {
        // ignore permission errors
      }
    }
  }

  console.log('\n' + green(bold('✓ Uninstall complete!')));
  console.log('  Files removed:  ' + removed);
  if (restored > 0) {
    console.log(yellow('  Backups restored: ' + restored));
  }
}

function status() {
  const agentDir = hermesAgentDir();
  const userPluginsDir = hermesPluginsDir();

  if (!fs.existsSync(agentDir)) {
    console.log(red('✖ Hermes agent directory not found at: ' + agentDir));
    console.log(yellow('  Is Hermes installed?'));
    process.exit(1);
  }

  const entries = getInstallEntries();
  let allOk = true;
  let installedCount = 0;

  console.log(bold('OpenRouter Routing Plugin Status\n'));

  for (const entry of entries) {
    const exists = fs.existsSync(entry.dst);
    const rel = path.relative(path.join(os.homedir(), '.hermes'), entry.dst);

    if (exists) {
      // Check if source and dest are in sync
      let upToDate = false;
      if (fs.existsSync(entry.src)) {
        const srcStat = fs.statSync(entry.src);
        const dstStat = fs.statSync(entry.dst);
        // Compare file sizes as a quick heuristic
        upToDate = srcStat.size === dstStat.size;
      }

      if (upToDate) {
        console.log('  ' + green('✔') + ' ' + cyan(rel) + '  ' + green('(up to date)'));
      } else {
        console.log('  ' + yellow('⚠') + ' ' + cyan(rel) + '  ' + yellow('(out of date — reinstall)'));
      }
      installedCount++;
    } else {
      console.log('  ' + red('✖') + ' ' + cyan(rel) + '  ' + red('(not installed)'));
      allOk = false;
    }
  }

  console.log('');
  if (installedCount === entries.length) {
    console.log(green(bold('✓ All plugins are installed.')));
  } else {
    console.log(yellow('⚠ Some plugins are missing. Run "' + bold('hermes-openrouter-routing install') + '" to install.'));
  }
}

function printHelp() {
  console.log(bold(PKG_NAME) + ' v' + PKG_VERSION);
  console.log('');
  console.log('  OpenRouter smart routing plugin installer for Hermes.');
  console.log('');
  console.log(bold('Usage:'));
  console.log('  ' + cyan('hermes-openrouter-routing install') + '      Install task router plugins');
  console.log('  ' + cyan('hermes-openrouter-routing uninstall') + '    Remove plugins and restore backups');
  console.log('  ' + cyan('hermes-openrouter-routing status') + '       Check installation status');
  console.log('  ' + cyan('hermes-openrouter-routing --version') + '    Print version');
  console.log('  ' + cyan('hermes-openrouter-routing --help') + '       Show this help');
  console.log('');
  console.log(bold('What it does:'));
  console.log('  1. Installs the OpenRouter model provider plugin with smart routing');
  console.log('  2. Installs the resolved-backend-model plugin for auto-routing visibility');
  console.log('  3. The smart routing classifier routes simple tasks to cheap models');
  console.log('     and complex tasks to powerful models');
  console.log('  4. Tool-call continuations skip routing');
  console.log('');
  console.log(bold('Configuration:'));
  console.log('  See README.md or run "hermes-openrouter-routing install" for config examples.');
  console.log('');
  console.log(bold('Repository:'));
  console.log('  https://github.com/Raithlin/hermes-openrouter-routing');
}

// ── Main ────────────────────────────────────────────────────────────

function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    printHelp();
    process.exit(0);
  }

  const cmd = args[0];

  switch (cmd) {
    case 'install':
      install();
      break;
    case 'uninstall':
      uninstall();
      break;
    case 'status':
      status();
      break;
    case '--version':
    case '-v':
      console.log(PKG_VERSION);
      break;
    case '--help':
    case '-h':
      printHelp();
      break;
    default:
      console.error(red('Unknown command: ' + cmd));
      console.error('Run "' + cyan('hermes-openrouter-routing --help') + '" for usage.');
      process.exit(1);
  }
}

main();
