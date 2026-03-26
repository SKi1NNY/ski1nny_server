const HANGUL_PATTERN = /[ㄱ-ㅎㅏ-ㅣ가-힣]/;
const TASK_ID_PATTERN = /\bT-\d+(?:-\d+)?\b/;

module.exports = {
  extends: ["@commitlint/config-conventional"],
  plugins: [
    {
      rules: {
        "no-task-id": (parsed) => {
          const text = [parsed.header, parsed.body, parsed.footer].filter(Boolean).join("\n");
          const hasTaskId = TASK_ID_PATTERN.test(text);
          return [
            !hasTaskId,
            "Commit message must not include task IDs like T-01 or T-87-1.",
          ];
        },
        "subject-has-korean": (parsed) => {
          const subject = (parsed.subject || "").trim();
          return [
            !subject || HANGUL_PATTERN.test(subject),
            "Commit subject must include Korean text.",
          ];
        },
        "body-bullet-list": (parsed) => {
          const body = (parsed.body || "").trim();
          if (!body) {
            return [true];
          }

          const invalidLine = body
            .split("\n")
            .find((line) => line.trim() && !line.trim().startsWith("- "));

          return [
            !invalidLine,
            "Commit body must use bullet lines starting with '- '.",
          ];
        },
      },
    },
  ],
  rules: {
    "body-empty": [2, "never"],
    "body-bullet-list": [2, "always"],
    "body-max-line-length": [2, "always", 72],
    "no-task-id": [2, "always"],
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "refactor", "docs", "chore", "test", "style"],
    ],
    "header-max-length": [2, "always", 72],
    "subject-empty": [2, "never"],
    "subject-has-korean": [2, "always"],
    "subject-case": [0],
    "subject-max-length": [2, "always", 50],
    "type-empty": [2, "never"],
  },
};
