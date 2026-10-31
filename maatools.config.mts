import path from "node:path";

export default {
    cwd: path.join(import.meta.dirname, "build/package"),
    maaVersion: "5.14.3",
    interfacePath: "interface.json",
    check: {},
};
