import { runCli } from "@nekosu/maa-tools";

const passed = await runCli("check", "maatools.config.mts");
process.exit(passed ? 0 : 1);
