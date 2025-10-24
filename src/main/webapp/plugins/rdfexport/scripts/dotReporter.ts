#!/usr/bin/env bun

/**
 * Pytest-style dot reporter for Bun tests
 * Wraps `bun test` and reformats output to show dots (., F, E, s)
 * 
 * Usage: bun run dotReporter.ts [test files or dirs...]
 */

import { spawn } from "child_process";

// ANSI color codes
const colors = {
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  cyan: "\x1b[36m",
  gray: "\x1b[90m",
  reset: "\x1b[0m",
  bold: "\x1b[1m",
};

interface TestResult {
  name: string;
  status: "pass" | "fail" | "skip";
  duration?: string;
  error?: string;
}

class DotReporter {
  private testResults: TestResult[] = [];
  private stdoutBuffer = "";
  private stderrBuffer = "";
  private dotsPerLine = 80;
  private dotCount = 0;
  private allOutput = "";
  private currentFile = "";
  private testsInCurrentFile = 0;
  private totalTests = 0;
  private bunSummaryLine = "";

  constructor() {}

  private printDot(char: string, color: string) {
    process.stdout.write(color + char + colors.reset);
    this.dotCount++;
    if (this.dotCount % this.dotsPerLine === 0) {
      process.stdout.write("\n");
    }
  }

  private parseTestLine(line: string): TestResult | null {
    // Match patterns like:
    // ✓ test name [0.88ms]
    // ✗ test name [1.05ms]
    // (pass) test name [0.48ms]
    // (fail) test name [0.48ms]
    
    // Check for pass patterns
    if (line.match(/^✓/) || line.includes("(pass)")) {
      const durationMatch = line.match(/\[([^\]]+)\]/);
      const name = line.replace(/^[✓\s]*(\(pass\))?/, "").replace(/\[[^\]]+\]/, "").trim();
      
      if (name) {
        return {
          name,
          status: "pass",
          duration: durationMatch ? durationMatch[1] : undefined,
        };
      }
    }

    // Check for fail patterns
    if (line.match(/^✗/) || line.includes("(fail)")) {
      const durationMatch = line.match(/\[([^\]]+)\]/);
      const name = line.replace(/^[✗\s]*(\(fail\))?/, "").replace(/\[[^\]]+\]/, "").trim();
      
      if (name) {
        return {
          name,
          status: "fail",
          duration: durationMatch ? durationMatch[1] : undefined,
        };
      }
    }

    // Check for skip patterns
    if (line.includes("(skip)") || line.match(/^s\s/)) {
      const name = line.replace(/(skip)/, "").replace(/\[[^\]]+\]/, "").trim();
      if (name) {
        return {
          name,
          status: "skip",
        };
      }
    }

    return null;
  }

  private extractFilePath(line: string): string | null {
    // Match patterns like "test/myfile.test.ts:" or "path/to/test.ts:"
    const match = line.match(/^([^\s]+\.test\.[tj]sx?):?\s*$/);
    return match && match[1] ? match[1] : null;
  }

  private printFileHeader(filePath: string) {
    if (this.dotCount % this.dotsPerLine !== 0 && this.dotCount > 0) {
      process.stdout.write("\n");
    }
    process.stdout.write(`${filePath} `);
  }

  private printProgress() {
    const percentage = Math.floor((this.totalTests / this.testResults.length) * 100);
    process.stdout.write(` ${colors.gray}[${percentage.toString().padStart(3)}%]${colors.reset}\n`);
  }

  private processLines(lines: string[]) {
    for (const line of lines) {
      if (!line.trim()) continue;
      
      // Check if this is a file header
      const filePath = this.extractFilePath(line);
      if (filePath && filePath !== this.currentFile) {
        if (this.currentFile && this.testsInCurrentFile > 0) {
          this.printProgress();
        }
        this.currentFile = filePath;
        this.testsInCurrentFile = 0;
        this.printFileHeader(filePath);
        this.dotCount = 0; // Reset for alignment
      }
      
      const testResult = this.parseTestLine(line);
      if (testResult) {
        this.testResults.push(testResult);
        this.testsInCurrentFile++;
        
        switch (testResult.status) {
          case "pass":
            this.printDot(".", colors.green);
            break;
          case "fail":
            this.printDot("F", colors.red);
            break;
          case "skip":
            this.printDot("s", colors.yellow);
            break;
        }
      }
      const bunSummaryMatch = line.match(/^Ran\s+\d+\s+tests\s+across\s+\d+\s+files?\.\s*\[[^\]]+\]/);
      if (bunSummaryMatch) {
        this.bunSummaryLine = bunSummaryMatch[0];
      }
    }
  }

  private printSummary() {
    // Print progress for last file
    if (this.currentFile && this.testsInCurrentFile > 0) {
      this.printProgress();
    }

    // Ensure we end the dots line
    if (this.dotCount % this.dotsPerLine !== 0) {
      process.stdout.write("\n");
    }
    process.stdout.write("\n");

    const passed = this.testResults.filter((t) => t.status === "pass").length;
    const failed = this.testResults.filter((t) => t.status === "fail").length;
    const skipped = this.testResults.filter((t) => t.status === "skip").length;

    // Print failed tests details
    if (failed > 0) {
      console.log(`${colors.red}${colors.bold}FAILURES${colors.reset}`);
      console.log("=".repeat(80));
      
      const failedTests = this.testResults.filter((t) => t.status === "fail");
      
      // Try to extract failure details from the full output
      const outputLines = this.allOutput.split("\n");
      
      failedTests.forEach((test, idx) => {
        console.log(`${colors.red}FAILED${colors.reset} ${test.name}`);
        
        // Look for error details in captured output
        let inError = false;
        let errorLines: string[] = [];
        
        for (let i = 0; i < outputLines.length; i++) {
          const line = outputLines[i];
          if (!line) continue;
          if (line.includes(test.name) && (line.includes("error:") || outputLines[i + 1]?.includes("error:"))) {
            inError = true;
            continue;
          }
          
          if (inError) {
            if (line.match(/^\d+ (pass|fail)/) || line.match(/^✓|^✗/) || line.trim() === "") {
              break;
            }
            errorLines.push(line);
          }
        }
        
        if (errorLines.length > 0) {
          console.log(errorLines.join("\n"));
        }
        
        if (idx < failedTests.length - 1) {
          console.log("-".repeat(80));
        }
      });
      console.log("=".repeat(80));
      console.log();
    }

    // Print summary line
    const parts = [];
    
    if (passed > 0) {
      parts.push(`${colors.green}${passed} passed${colors.reset}`);
    }
    if (failed > 0) {
      parts.push(`${colors.red}${failed} failed${colors.reset}`);
    }
    if (skipped > 0) {
      parts.push(`${colors.yellow}${skipped} skipped${colors.reset}`);
    }

    const total = passed + failed + skipped;
    
    if (total > 0) {
      console.log(
        `${parts.join(", ")}\n${colors.cyan}${this.bunSummaryLine || ""}${colors.reset}`
      );
    } else {
      console.log(`${colors.gray}No tests found${colors.reset}`);
    }
    
    // Exit with appropriate code
    process.exit(failed > 0 ? 1 : 0);
  }

  async run(args: string[]) {
    console.log(`${colors.cyan}Running Bun tests...${colors.reset}\n`);
    
    // Run bun test with all passed arguments
    const bunArgs = ["test", ...args];
    const bunProcess = spawn("bun", bunArgs, {
      stdio: ["inherit", "pipe", "pipe"],
    });

    bunProcess.stdout.on("data", (data: Buffer) => {
      const output = data.toString();
      this.allOutput += output;
      this.stdoutBuffer += output;

      // Process complete lines immediately for streaming
      const lines = this.stdoutBuffer.split("\n");
      this.stdoutBuffer = lines.pop() || "";

      this.processLines(lines);
    });

    bunProcess.stderr.on("data", (data: Buffer) => {
      const output = data.toString();
      this.allOutput += output;
      this.stderrBuffer += output;

      // Process complete lines immediately for streaming
      const lines = this.stderrBuffer.split("\n");
      this.stderrBuffer = lines.pop() || "";

      this.processLines(lines);
    });

    bunProcess.on("close", (code) => {
      // Process any remaining buffer
      if (this.stdoutBuffer.trim()) {
        this.processLines([this.stdoutBuffer]);
      }
      if (this.stderrBuffer.trim()) {
        this.processLines([this.stderrBuffer]);
      }

      this.totalTests = this.testResults.length;
      
      this.printSummary();
    });
  }
}

// Main execution
const args = process.argv.slice(2);
const reporter = new DotReporter();
reporter.run(args);
