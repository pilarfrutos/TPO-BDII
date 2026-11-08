// One-shot autenticado. Nunca imprime credenciales ni reconfigura un set existente.
const expected = {_id: "rs0", members: [{_id: 0, host: "mongo:27017"}]};
let initiated = false;
for (let attempt = 0; attempt < 90; attempt++) {
    let connection;
    try {
        connection = new Mongo("mongodb://mongo:27017/admin?directConnection=true&serverSelectionTimeoutMS=2000&connectTimeoutMS=2000");
        const admin = connection.getDB("admin");
        const auth = admin.auth(process.env.MONGO_INITDB_ROOT_USERNAME,
                                process.env.MONGO_INITDB_ROOT_PASSWORD);
        if (!auth.ok) {
            print("MongoDB: autenticación rechazada; revisar las credenciales originales.");
            quit(1);
        }
        let current;
        try {
            current = admin.runCommand({replSetGetConfig: 1});
        } catch (error) {
            if (error.code !== 94) throw error;
            current = {code: 94};
        }
        if (current.code === 94) { // NotYetInitialized
            try {
                const result = admin.runCommand({replSetInitiate: expected});
                initiated = result.ok === 1;
            } catch (error) {
                // Otra ejecución concurrente puede haberse adelantado.
                if (error.code !== 23) throw error;
            }
        } else {
            if (!current.ok) throw new Error("config pending");
            const config = current.config;
            if (config._id !== expected._id || config.members.length !== 1 ||
                config.members[0].host !== expected.members[0].host) {
                print("Replica set incompatible: se conserva su configuración; revisar manualmente.");
                quit(1);
            }
            const hello = admin.runCommand({hello: 1});
            if (hello.setName === "rs0" && hello.isWritablePrimary) {
                print(initiated ? "Replica set rs0 inicializado; PRIMARY disponible."
                                : "Replica set rs0 existente conservado; PRIMARY disponible.");
                quit(0);
            }
        }
    } catch (error) {
        if (error.code === 18 || error.code === 13) {
            print("MongoDB: autenticación o permisos insuficientes; revisar .env sin borrar volúmenes.");
            quit(1);
        }
        // Durante el arranque oficial el servidor temporal solo escucha en localhost.
        // Los errores de red se reintentan sin imprimir URIs ni mensajes sensibles.
    } finally {
        if (connection) connection.close();
    }
    sleep(1000);
}
print("No se obtuvo PRIMARY a tiempo; revisar estado de mongo y ejecutar de nuevo la inicialización.");
quit(1);
