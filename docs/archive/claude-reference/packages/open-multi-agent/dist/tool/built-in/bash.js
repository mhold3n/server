/**
 * Built-in bash tool.
 *
 * Executes a shell command and returns its stdout + stderr.  Supports an
 * optional timeout and a custom working directory.
 */
import { spawn } from 'child_process';
import { z } from 'zod';
import { defineTool } from '../framework.js';
// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const DEFAULT_TIMEOUT_MS = 30_000;
// ---------------------------------------------------------------------------
// Tool definition
// ---------------------------------------------------------------------------
export const bashTool = defineTool({
    name: 'bash',
    description: 'Execute a bash command and return its stdout and stderr. ' +
        'Use this for file system operations, running scripts, installing packages, ' +
        'and any task that requires shell access. ' +
        'The command runs in a non-interactive shell (bash -c). ' +
        'Long-running commands should use the timeout parameter.',
    inputSchema: z.object({
        command: z.string().describe('The bash command to execute.'),
        timeout: z
            .number()
            .optional()
            .describe(`Timeout in milliseconds before the command is forcibly killed. ` +
            `Defaults to ${DEFAULT_TIMEOUT_MS} ms.`),
        cwd: z
            .string()
            .optional()
            .describe('Working directory in which to run the command.'),
    }),
    execute: async (input, context) => {
        const timeoutMs = input.timeout ?? DEFAULT_TIMEOUT_MS;
        const { stdout, stderr, exitCode } = await runCommand(input.command, { cwd: input.cwd, timeoutMs }, context.abortSignal);
        const combined = buildOutput(stdout, stderr, exitCode);
        const isError = exitCode !== 0;
        return {
            data: combined,
            isError,
        };
    },
});
/**
 * Spawn a bash subprocess, capture its output, and resolve when it exits or
 * the abort signal fires.
 */
function runCommand(command, options, signal) {
    return new Promise((resolve) => {
        const stdoutChunks = [];
        const stderrChunks = [];
        const child = spawn('bash', ['-c', command], {
            cwd: options.cwd,
            env: process.env,
            stdio: ['ignore', 'pipe', 'pipe'],
        });
        child.stdout.on('data', (chunk) => stdoutChunks.push(chunk));
        child.stderr.on('data', (chunk) => stderrChunks.push(chunk));
        let timedOut = false;
        let settled = false;
        const done = (exitCode) => {
            if (settled)
                return;
            settled = true;
            clearTimeout(timer);
            if (signal !== undefined) {
                signal.removeEventListener('abort', onAbort);
            }
            const stdout = Buffer.concat(stdoutChunks).toString('utf8');
            const stderr = Buffer.concat(stderrChunks).toString('utf8');
            resolve({ stdout, stderr, exitCode });
        };
        // Timeout handler
        const timer = setTimeout(() => {
            timedOut = true;
            child.kill('SIGKILL');
        }, options.timeoutMs);
        // Abort-signal handler
        const onAbort = () => {
            child.kill('SIGKILL');
        };
        if (signal !== undefined) {
            signal.addEventListener('abort', onAbort, { once: true });
        }
        child.on('close', (code) => {
            const exitCode = code ?? (timedOut ? 124 : 1);
            done(exitCode);
        });
        child.on('error', (err) => {
            if (!settled) {
                settled = true;
                clearTimeout(timer);
                if (signal !== undefined) {
                    signal.removeEventListener('abort', onAbort);
                }
                resolve({
                    stdout: '',
                    stderr: err.message,
                    exitCode: 127,
                });
            }
        });
    });
}
/**
 * Format captured output into a single readable string.
 * When only stdout is present its content is returned as-is.
 * When stderr is also present both sections are labelled.
 */
function buildOutput(stdout, stderr, exitCode) {
    const parts = [];
    if (stdout.length > 0) {
        parts.push(stdout);
    }
    if (stderr.length > 0) {
        parts.push(stdout.length > 0
            ? `--- stderr ---\n${stderr}`
            : stderr);
    }
    if (parts.length === 0) {
        return exitCode === 0
            ? '(command completed with no output)'
            : `(command exited with code ${exitCode}, no output)`;
    }
    if (exitCode !== 0 && parts.length > 0) {
        parts.push(`\n(exit code: ${exitCode})`);
    }
    return parts.join('\n');
}
//# sourceMappingURL=bash.js.map