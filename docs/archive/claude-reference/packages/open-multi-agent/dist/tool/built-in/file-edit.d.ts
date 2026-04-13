/**
 * Built-in file-edit tool.
 *
 * Performs a targeted string replacement inside an existing file.
 * The uniqueness invariant (one match unless replace_all is set) prevents the
 * common class of bugs where a generic pattern matches the wrong occurrence.
 */
export declare const fileEditTool: import("../framework.js").ToolDefinition<{
    path: string;
    old_string: string;
    new_string: string;
    replace_all?: boolean | undefined;
}>;
//# sourceMappingURL=file-edit.d.ts.map