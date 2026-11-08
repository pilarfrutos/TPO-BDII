try {
    const connection = new Mongo("mongodb://localhost:27017/admin?directConnection=true&serverSelectionTimeoutMS=2000");
    const admin = connection.getDB("admin");
    if (!admin.auth(process.env.MONGO_INITDB_ROOT_USERNAME,
                    process.env.MONGO_INITDB_ROOT_PASSWORD).ok) quit(1);
    const hello = admin.runCommand({hello: 1});
    quit(hello.setName === "rs0" && hello.isWritablePrimary ? 0 : 1);
} catch (_) {
    quit(1);
}
