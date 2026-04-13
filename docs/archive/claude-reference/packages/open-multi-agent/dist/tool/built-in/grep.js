/**
 * Built-in grep tool.
 *
 * Searches for a regex pattern in files.  Prefers the `rg` (ripgrep) binary
 * when available for performance; falls back to a pure Node.js recursive
 * implementation using the standard `fs` module so the tool works in
 * environments without ripgrep installed.
 */
import { spawn } from 'child_process';
import { readdir, readFile, stat } from 'fs/promises';
// Note: readdir is used with { encoding: 'utf8' } to return string[] directly.
import { join, relative } from 'path';
import { z } from 'zod';
import { defineTool } from '../framework.js';
// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DEFAULT_MAX_RESULTS = 100;
// Directories that are almost never useful to search inside
const SKIP_DIRS = new Set([
    '.git',
    '.svn',
    '.hg',
    'node_modules',
    '.next',
    'dist',
    'build',
]);
// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------
export const grepTool = defineTool({
    name: 'grep',
    description: 'Search for a regular-expression pattern in one or more files. ' +
        'Returns matching lines with their file paths and 1-based line numbers. ' +
        'Use the `glob` parameter to restrict the search to specific file types ' +
        '(e.g. "*.ts"). ' +
        'Results are capped by `maxResults` to keep the response manageable.',
    inputSchema: z.object({
        pattern: z
            .string()
            .describe('Regular expression pattern to search for in file contents.'),
        path: z
            .string()
            .optional()
            .describe('Directory or file path to search in. ' +
            'Defaults to the current working directory.'),
        glob: z
            .string()
            .optional()
            .describe('Glob pattern to filter which files are searched ' +
            '(e.g. "*.ts", "**/*.json"). ' +
            'Only used when `path` is a directory.'),
        maxResults: z
            .number()
            .int()
            .positive()
            .optional()
            .describe(`Maximum number of matching lines to return. ` +
            `Defaults to ${DEFAULT_MAX_RESULTS}.`),
    }),
    execute: async (input, context) => {
        const searchPath = input.path ?? process.cwd();
        const maxResults = input.maxResults ?? DEFAULT_MAX_RESULTS;
        // Compile the regex once and surface bad patterns immediately.
        let regex;
        try {
            regex = new RegExp(input.pattern);
        }
        catch {
            return {
                data: `Invalid regular expression: "${input.pattern}"`,
                isError: true,
            };
        }
        // Attempt ripgrep first.
        const rgAvailable = await isRipgrepAvailable();
        if (rgAvailable) {
            return runRipgrep(input.pattern, searchPath, {
                glob: input.glob,
                maxResults,
                signal: context.abortSignal,
            });
        }
        // Fallback: pure Node.js recursive search.
        return runNodeSearch(regex, searchPath, {
            glob: input.glob,
            maxResults,
            signal: context.abortSignal,
        });
    },
});
async function runRipgrep(pattern, searchPath, options) {
    const args = [
        '--line-number',
        '--no-heading',
        '--color=never',
        `--max-count=${options.maxResults}`,
    ];
    if (options.glob !== undefined) {
        args.push('--glob', options.glob);
    }
    args.push('--', pattern, searchPath);
    return new Promise((resolve) => {
        const chunks = [];
        const errChunks = [];
        const child = spawn('rg', args, { stdio: ['ignore', 'pipe', 'pipe'] });
        child.stdout.on('data', (d) => chunks.push(d));
        child.stderr.on('data', (d) => errChunks.push(d));
        const onAbort = () => { child.kill('SIGKILL'); };
        if (options.signal !== undefined) {
            options.signal.addEventListener('abort', onAbort, { once: true });
        }
        child.on('close', (code) => {
            if (options.signal !== undefined) {
                options.signal.removeEventListener('abort', onAbort);
            }
            const output = Buffer.concat(chunks).toString('utf8').trimEnd();
            // rg exit code 1 = no matches (not an error)
            if (code !== 0 && code !== 1) {
                const errMsg = Buffer.concat(errChunks).toString('utf8').trim();
                resolve({
                    data: `ripgrep failed (exit ${code}): ${errMsg}`,
                    isError: true,
                });
                return;
            }
            if (output.length === 0) {
                resolve({ data: 'No matches found.', isError: false });
                return;
            }
            const lines = output.split('\n');
            resolve({
                data: lines.join('\n'),
                isError: false,
            });
        });
        child.on('error', () => {
            if (options.signal !== undefined) {
                options.signal.removeEventListener('abort', onAbort);
            }
            // Caller will see an error result — the tool won't retry with Node search
            // since this branch is only reachable after we confirmed rg is available.
            resolve({
                data: 'ripgrep process error — run may be retried with the Node.js fallback.',
                isError: true,
            });
        });
    });
}
async function runNodeSearch(regex, searchPath, options) {
    // Collect files
    let files;
    try {
        const info = await stat(searchPath);
        if (info.isFile()) {
            files = [searchPath];
        }
        else {
            files = await collectFiles(searchPath, options.glob, options.signal);
        }
    }
    catch (err) {
        const message = err instanceof Error ? err.message : 'Unknown error';
        return {
            data: `Cannot access path "${searchPath}": ${message}`,
            isError: true,
        };
    }
    const matches = [];
    for (const file of files) {
        if (options.signal?.aborted === true)
            break;
        if (matches.length >= options.maxResults)
            break;
        let fileContent;
        try {
            fileContent = (await readFile(file)).toString('utf8');
        }
        catch {
            // Skip unreadable files (binary, permission denied, etc.)
            continue;
        }
        const lines = fileContent.split('\n');
        for (let i = 0; i < lines.length; i++) {
            if (matches.length >= options.maxResults)
                break;
            // Reset lastIndex for global regexes
            regex.lastIndex = 0;
            if (regex.test(lines[i])) {
                matches.push({
                    file: relative(process.cwd(), file) || file,
                    lineNumber: i + 1,
                    text: lines[i],
                });
            }
        }
    }
    if (matches.length === 0) {
        return { data: 'No matches found.', isError: false };
    }
    const formatted = matches
        .map((m) => `${m.file}:${m.lineNumber}:${m.text}`)
        .join('\n');
    const truncationNote = matches.length >= options.maxResults
        ? `\n\n(results capped at ${options.maxResults}; use maxResults to raise the limit)`
        : '';
    return {
        data: formatted + truncationNote,
        isError: false,
    };
}
// ---------------------------------------------------------------------------
// File collection with glob filtering
// ---------------------------------------------------------------------------
/**
 * Recursively walk `dir` and return file paths, honouring `SKIP_DIRS` and an
 * optional glob pattern.
 */
async function collectFiles(dir, glob, signal) {
    const results = [];
    await walk(dir, glob, results, signal);
    return results;
}
async function walk(dir, glob, results, signal) {
    if (signal?.aborted === true)
        return;
    let entryNames;
    try {
        // Read as plain strings so we don't have to deal with Buffer Dirent variants.
        entryNames = await readdir(dir, { encoding: 'utf8' });
    }
    catch {
        return;
    }
    for (const entryName of entryNames) {
        if (signal !== undefined && signal.aborted)
            return;
        const fullPath = join(dir, entryName);
        let entryInfo;
        try {
            entryInfo = await stat(fullPath);
        }
        catch {
            continue;
        }
        if (entryInfo.isDirectory()) {
            if (!SKIP_DIRS.has(entryName)) {
                await walk(fullPath, glob, results, signal);
            }
        }
        else if (entryInfo.isFile()) {
            if (glob === undefined || matchesGlob(entryName, glob)) {
                results.push(fullPath);
            }
        }
    }
}
/**
 * Minimal glob match supporting `*.ext` and `**\/<pattern>` forms.
 */
function matchesGlob(filename, glob) {
    // Strip leading **/ prefix — we already recurse into all directories
    const pattern = glob.startsWith('**/') ? glob.slice(3) : glob;
    // Convert shell glob characters to regex equivalents
    const regexSource = pattern
        .replace(/[.+^${}()|[\]\\]/g, '\\$&') // escape special regex chars first
        .replace(/\*/g, '.*') // * -> .*
        .replace(/\?/g, '.'); // ? -> .
    const re = new RegExp(`^${regexSource}$`, 'i');
    return re.test(filename);
}
// ---------------------------------------------------------------------------
// ripgrep availability check (cached per process)
// ---------------------------------------------------------------------------
let rgAvailableCache;
async function isRipgrepAvailable() {
    if (rgAvailableCache !== undefined)
        return rgAvailableCache;
    rgAvailableCache = await new Promise((resolve) => {
        const child = spawn('rg', ['--version'], { stdio: 'ignore' });
        child.on('close', (code) => resolve(code === 0));
        child.on('error', () => resolve(false));
    });
    return rgAvailableCache;
}
//# sourceMappingURL=grep.js.map