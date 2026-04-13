import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import { Octokit } from '@octokit/rest';
import dotenv from 'dotenv';

// Load environment variables
dotenv.config();

interface GitHubConfig {
  token: string;
  owner?: string;
  repo?: string;
}

class GitHubMCPServer {
  private server: Server;
  private octokit: Octokit;
  private config: GitHubConfig;

  constructor() {
    this.config = {
      token: process.env.GITHUB_TOKEN || '',
      owner: process.env.GITHUB_OWNER,
      repo: process.env.GITHUB_REPO,
    };

    if (!this.config.token) {
      throw new Error('GITHUB_TOKEN environment variable is required');
    }

    this.octokit = new Octokit({
      auth: this.config.token,
    });

    this.server = new Server(
      {
        name: 'github-mcp-server',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupHandlers();
  }

  private setupHandlers(): void {
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      return {
        tools: [
          {
            name: 'search_repositories',
            description: 'Search for repositories on GitHub',
            inputSchema: {
              type: 'object',
              properties: {
                query: {
                  type: 'string',
                  description: 'Search query',
                },
                sort: {
                  type: 'string',
                  enum: ['stars', 'forks', 'help-wanted-issues', 'updated'],
                  description: 'Sort order',
                },
                order: {
                  type: 'string',
                  enum: ['asc', 'desc'],
                  description: 'Sort direction',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['query'],
            },
          },
          {
            name: 'get_repository',
            description: 'Get information about a specific repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
              },
              required: ['owner', 'repo'],
            },
          },
          {
            name: 'list_issues',
            description: 'List issues for a repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                state: {
                  type: 'string',
                  enum: ['open', 'closed', 'all'],
                  description: 'Issue state',
                },
                labels: {
                  type: 'string',
                  description: 'Comma-separated list of labels',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['owner', 'repo'],
            },
          },
          {
            name: 'create_issue',
            description: 'Create a new issue',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                title: {
                  type: 'string',
                  description: 'Issue title',
                },
                body: {
                  type: 'string',
                  description: 'Issue body',
                },
                labels: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Issue labels',
                },
                assignees: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Issue assignees',
                },
              },
              required: ['owner', 'repo', 'title'],
            },
          },
          {
            name: 'list_pull_requests',
            description: 'List pull requests for a repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                state: {
                  type: 'string',
                  enum: ['open', 'closed', 'all'],
                  description: 'Pull request state',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['owner', 'repo'],
            },
          },
          {
            name: 'get_file_contents',
            description: 'Get the contents of a file from a repository',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                path: {
                  type: 'string',
                  description: 'File path',
                },
                ref: {
                  type: 'string',
                  description: 'Branch, tag, or commit SHA',
                },
              },
              required: ['owner', 'repo', 'path'],
            },
          },
          {
            name: 'list_projects',
            description: 'List GitHub projects for an organization or user',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Organization or user name',
                },
                state: {
                  type: 'string',
                  enum: ['open', 'closed', 'all'],
                  description: 'Project state filter',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['owner'],
            },
          },
          {
            name: 'get_project',
            description: 'Get information about a specific GitHub project',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'number',
                  description: 'Project ID',
                },
              },
              required: ['project_id'],
            },
          },
          {
            name: 'create_project',
            description: 'Create a new GitHub project',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Organization or user name',
                },
                name: {
                  type: 'string',
                  description: 'Project name',
                },
                body: {
                  type: 'string',
                  description: 'Project description',
                },
                public: {
                  type: 'boolean',
                  description: 'Whether the project should be public',
                },
              },
              required: ['owner', 'name'],
            },
          },
          {
            name: 'list_project_items',
            description: 'List items (issues, PRs) in a GitHub project',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'number',
                  description: 'Project ID',
                },
                per_page: {
                  type: 'number',
                  minimum: 1,
                  maximum: 100,
                  description: 'Number of results per page',
                },
              },
              required: ['project_id'],
            },
          },
          {
            name: 'add_issue_to_project',
            description: 'Add an issue to a GitHub project',
            inputSchema: {
              type: 'object',
              properties: {
                project_id: {
                  type: 'number',
                  description: 'Project ID',
                },
                issue_id: {
                  type: 'number',
                  description: 'Issue ID',
                },
                field_id: {
                  type: 'string',
                  description: 'Field ID for custom fields (optional)',
                },
                value: {
                  type: 'string',
                  description: 'Field value (optional)',
                },
              },
              required: ['project_id', 'issue_id'],
            },
          },
          {
            name: 'apply_issue_template',
            description: 'Apply an issue template to create a structured issue',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                template_name: {
                  type: 'string',
                  description: 'Template name (e.g., bug_report, feature_request)',
                },
                title: {
                  type: 'string',
                  description: 'Issue title',
                },
                template_data: {
                  type: 'object',
                  description: 'Template data to fill in',
                },
                labels: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Issue labels',
                },
                assignees: {
                  type: 'array',
                  items: { type: 'string' },
                  description: 'Issue assignees',
                },
              },
              required: ['owner', 'repo', 'template_name', 'title'],
            },
          },
          {
            name: 'create_pull_request',
            description: 'Create a pull request',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                title: {
                  type: 'string',
                  description: 'Pull request title',
                },
                head: {
                  type: 'string',
                  description: 'Head branch name',
                },
                base: {
                  type: 'string',
                  description: 'Base branch name',
                },
                body: {
                  type: 'string',
                  description: 'Pull request body',
                },
                draft: {
                  type: 'boolean',
                  description: 'Whether to create as draft',
                },
                maintainer_can_modify: {
                  type: 'boolean',
                  description: 'Whether maintainers can modify',
                },
              },
              required: ['owner', 'repo', 'title', 'head', 'base'],
            },
          },
          {
            name: 'link_pr_to_issue',
            description: 'Link a pull request to an issue',
            inputSchema: {
              type: 'object',
              properties: {
                owner: {
                  type: 'string',
                  description: 'Repository owner',
                },
                repo: {
                  type: 'string',
                  description: 'Repository name',
                },
                pull_number: {
                  type: 'number',
                  description: 'Pull request number',
                },
                issue_number: {
                  type: 'number',
                  description: 'Issue number to link',
                },
              },
              required: ['owner', 'repo', 'pull_number', 'issue_number'],
            },
          },
        ],
      };
    });

    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;

      try {
        switch (name) {
          case 'search_repositories':
            return await this.searchRepositories(args as any);
          case 'get_repository':
            return await this.getRepository(args as any);
          case 'list_issues':
            return await this.listIssues(args as any);
          case 'create_issue':
            return await this.createIssue(args as any);
          case 'list_pull_requests':
            return await this.listPullRequests(args as any);
          case 'get_file_contents':
            return await this.getFileContents(args as any);
          case 'list_projects':
            return await this.listProjects(args as any);
          case 'get_project':
            return await this.getProject(args as any);
          case 'create_project':
            return await this.createProject(args as any);
          case 'list_project_items':
            return await this.listProjectItems(args as any);
          case 'add_issue_to_project':
            return await this.addIssueToProject(args as any);
          case 'apply_issue_template':
            return await this.applyIssueTemplate(args as any);
          case 'create_pull_request':
            return await this.createPullRequest(args as any);
          case 'link_pr_to_issue':
            return await this.linkPrToIssue(args as any);
          default:
            throw new Error(`Unknown tool: ${name}`);
        }
      } catch (error) {
        return {
          content: [
            {
              type: 'text',
              text: `Error: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
        };
      }
    });
  }

  private async searchRepositories(args: {
    query: string;
    sort?: string;
    order?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.search.repos({
      q: args.query,
      sort: args.sort as any,
      order: args.order as any,
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              total_count: data.total_count,
              repositories: data.items.map((repo) => ({
                name: repo.name,
                full_name: repo.full_name,
                description: repo.description,
                html_url: repo.html_url,
                stars: repo.stargazers_count,
                forks: repo.forks_count,
                language: repo.language,
                updated_at: repo.updated_at,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async getRepository(args: { owner: string; repo: string }) {
    const { data } = await this.octokit.repos.get({
      owner: args.owner,
      repo: args.repo,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              name: data.name,
              full_name: data.full_name,
              description: data.description,
              html_url: data.html_url,
              clone_url: data.clone_url,
              stars: data.stargazers_count,
              forks: data.forks_count,
              language: data.language,
              created_at: data.created_at,
              updated_at: data.updated_at,
              default_branch: data.default_branch,
              topics: data.topics,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async listIssues(args: {
    owner: string;
    repo: string;
    state?: string;
    labels?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.issues.listForRepo({
      owner: args.owner,
      repo: args.repo,
      state: (args.state as any) || 'open',
      labels: args.labels,
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              issues: data.map((issue) => ({
                number: issue.number,
                title: issue.title,
                body: issue.body,
                state: issue.state,
                html_url: issue.html_url,
                labels: issue.labels.map((label) => ({
                  name: label.name,
                  color: label.color,
                })),
                assignees: issue.assignees.map((assignee) => ({
                  login: assignee.login,
                  html_url: assignee.html_url,
                })),
                created_at: issue.created_at,
                updated_at: issue.updated_at,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async createIssue(args: {
    owner: string;
    repo: string;
    title: string;
    body?: string;
    labels?: string[];
    assignees?: string[];
  }) {
    const { data } = await this.octokit.issues.create({
      owner: args.owner,
      repo: args.repo,
      title: args.title,
      body: args.body,
      labels: args.labels,
      assignees: args.assignees,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              number: data.number,
              title: data.title,
              body: data.body,
              state: data.state,
              html_url: data.html_url,
              labels: data.labels.map((label) => ({
                name: label.name,
                color: label.color,
              })),
              assignees: data.assignees.map((assignee) => ({
                login: assignee.login,
                html_url: assignee.html_url,
              })),
              created_at: data.created_at,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async listPullRequests(args: {
    owner: string;
    repo: string;
    state?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.pulls.list({
      owner: args.owner,
      repo: args.repo,
      state: (args.state as any) || 'open',
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              pull_requests: data.map((pr) => ({
                number: pr.number,
                title: pr.title,
                body: pr.body,
                state: pr.state,
                html_url: pr.html_url,
                head: {
                  ref: pr.head.ref,
                  sha: pr.head.sha,
                },
                base: {
                  ref: pr.base.ref,
                  sha: pr.base.sha,
                },
                user: {
                  login: pr.user?.login,
                  html_url: pr.user?.html_url,
                },
                created_at: pr.created_at,
                updated_at: pr.updated_at,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async getFileContents(args: {
    owner: string;
    repo: string;
    path: string;
    ref?: string;
  }) {
    const { data } = await this.octokit.repos.getContent({
      owner: args.owner,
      repo: args.repo,
      path: args.path,
      ref: args.ref,
    });

    if (Array.isArray(data)) {
      // Directory listing
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                type: 'directory',
                path: args.path,
                contents: data.map((item) => ({
                  name: item.name,
                  type: item.type,
                  path: item.path,
                  size: item.size,
                  download_url: item.download_url,
                })),
              },
              null,
              2
            ),
          },
        ],
      };
    } else {
      // File content
      const content = Buffer.from(data.content, 'base64').toString('utf-8');
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(
              {
                type: 'file',
                name: data.name,
                path: data.path,
                size: data.size,
                content: content,
                encoding: data.encoding,
                download_url: data.download_url,
              },
              null,
              2
            ),
          },
        ],
      };
    }
  }

  private async listProjects(args: {
    owner: string;
    state?: string;
    per_page?: number;
  }) {
    const { data } = await this.octokit.projects.listForUser({
      username: args.owner,
      state: (args.state as any) || 'open',
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              projects: data.map((project) => ({
                id: project.id,
                name: project.name,
                body: project.body,
                state: project.state,
                html_url: project.html_url,
                created_at: project.created_at,
                updated_at: project.updated_at,
                creator: {
                  login: project.creator?.login,
                  html_url: project.creator?.html_url,
                },
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async getProject(args: { project_id: number }) {
    const { data } = await this.octokit.projects.get({
      project_id: args.project_id,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              id: data.id,
              name: data.name,
              body: data.body,
              state: data.state,
              html_url: data.html_url,
              created_at: data.created_at,
              updated_at: data.updated_at,
              creator: {
                login: data.creator?.login,
                html_url: data.creator?.html_url,
              },
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async createProject(args: {
    owner: string;
    name: string;
    body?: string;
    public?: boolean;
  }) {
    const { data } = await this.octokit.projects.createForUser({
      username: args.owner,
      name: args.name,
      body: args.body,
      public: args.public !== false, // Default to public
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              id: data.id,
              name: data.name,
              body: data.body,
              state: data.state,
              html_url: data.html_url,
              created_at: data.created_at,
              creator: {
                login: data.creator?.login,
                html_url: data.creator?.html_url,
              },
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async listProjectItems(args: {
    project_id: number;
    per_page?: number;
  }) {
    const { data } = await this.octokit.projects.listCards({
      project_id: args.project_id,
      per_page: args.per_page || 10,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              items: data.map((card) => ({
                id: card.id,
                note: card.note,
                archived: card.archived,
                created_at: card.created_at,
                updated_at: card.updated_at,
                content_url: card.content_url,
                content_type: card.content_type,
              })),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async addIssueToProject(args: {
    project_id: number;
    issue_id: number;
    field_id?: string;
    value?: string;
  }) {
    // First, create a project card for the issue
    const { data: card } = await this.octokit.projects.createCard({
      project_id: args.project_id,
      content_id: args.issue_id,
      content_type: 'Issue',
    });

    // If custom field is provided, update the field value
    if (args.field_id && args.value) {
      await this.octokit.projects.updateProjectItem({
        project_id: args.project_id,
        item_id: card.id,
        field_id: args.field_id,
        value: args.value,
      });
    }

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              card_id: card.id,
              project_id: args.project_id,
              issue_id: args.issue_id,
              field_updated: !!(args.field_id && args.value),
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async applyIssueTemplate(args: {
    owner: string;
    repo: string;
    template_name: string;
    title: string;
    template_data?: any;
    labels?: string[];
    assignees?: string[];
  }) {
    // Get the issue template
    const templatePath = `.github/ISSUE_TEMPLATE/${args.template_name}.md`;
    
    let templateContent = '';
    try {
      const { data: templateFile } = await this.octokit.repos.getContent({
        owner: args.owner,
        repo: args.repo,
        path: templatePath,
      });
      
      if (!Array.isArray(templateFile)) {
        templateContent = Buffer.from(templateFile.content, 'base64').toString('utf-8');
      }
    } catch (error) {
      // Template not found, use default template
      templateContent = `## Description\n\n## Steps to Reproduce\n\n## Expected Behavior\n\n## Actual Behavior\n\n## Additional Information`;
    }

    // Fill in template data if provided
    if (args.template_data) {
      for (const [key, value] of Object.entries(args.template_data)) {
        templateContent = templateContent.replace(new RegExp(`{{${key}}}`, 'g'), String(value));
      }
    }

    // Create the issue with the template
    const { data } = await this.octokit.issues.create({
      owner: args.owner,
      repo: args.repo,
      title: args.title,
      body: templateContent,
      labels: args.labels,
      assignees: args.assignees,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              number: data.number,
              title: data.title,
              body: data.body,
              state: data.state,
              html_url: data.html_url,
              labels: data.labels.map((label) => ({
                name: label.name,
                color: label.color,
              })),
              assignees: data.assignees.map((assignee) => ({
                login: assignee.login,
                html_url: assignee.html_url,
              })),
              created_at: data.created_at,
              template_used: args.template_name,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async createPullRequest(args: {
    owner: string;
    repo: string;
    title: string;
    head: string;
    base: string;
    body?: string;
    draft?: boolean;
    maintainer_can_modify?: boolean;
  }) {
    const { data } = await this.octokit.pulls.create({
      owner: args.owner,
      repo: args.repo,
      title: args.title,
      head: args.head,
      base: args.base,
      body: args.body,
      draft: args.draft || false,
      maintainer_can_modify: args.maintainer_can_modify !== false,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              number: data.number,
              title: data.title,
              body: data.body,
              state: data.state,
              html_url: data.html_url,
              head: {
                ref: data.head.ref,
                sha: data.head.sha,
              },
              base: {
                ref: data.base.ref,
                sha: data.base.sha,
              },
              user: {
                login: data.user?.login,
                html_url: data.user?.html_url,
              },
              created_at: data.created_at,
              draft: data.draft,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  private async linkPrToIssue(args: {
    owner: string;
    repo: string;
    pull_number: number;
    issue_number: number;
  }) {
    // Add a comment to the PR linking to the issue
    const comment = `Closes #${args.issue_number}`;
    
    const { data } = await this.octokit.issues.createComment({
      owner: args.owner,
      repo: args.repo,
      issue_number: args.pull_number,
      body: comment,
    });

    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(
            {
              comment_id: data.id,
              pull_number: args.pull_number,
              issue_number: args.issue_number,
              link_comment: comment,
              html_url: data.html_url,
            },
            null,
            2
          ),
        },
      ],
    };
  }

  async run(): Promise<void> {
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('GitHub MCP server running on stdio');
  }
}

// Start the server
const server = new GitHubMCPServer();
server.run().catch((error) => {
  console.error('Failed to start GitHub MCP server:', error);
  process.exit(1);
});
