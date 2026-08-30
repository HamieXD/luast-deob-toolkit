--[[
Generic read-only runtime probe for Roblox deobfuscation work.

Safety properties:
- Does NOT FireServer / InvokeServer.
- Does NOT hook metamethods/functions.
- Does NOT require arbitrary unloaded ModuleScripts.
- It may require ModuleScripts already reported by getloadedmodules(), because
  require() should return their cached result rather than initialize a new one.

Optional hints:
getgenv().__DEOB_PROBE_HINTS = {
    moduleNames = {"Network", "Replication", "Library"},
    configNames = {"Farmers", "ItemShop", "Upgrade Tree", "Rebirths", "Expand", "Sprinklers", "Fertilizer"},
    dataKeys = {"inventory", "farmers", "stats", "money", "discovered", "upgrade_tree"},
}
]]

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local LocalPlayer = Players.LocalPlayer
local env = (getgenv and getgenv()) or _G

local Hints = env.__DEOB_PROBE_HINTS or {}
Hints.moduleNames = Hints.moduleNames or {"Network", "Replication", "Library"}
Hints.configNames = Hints.configNames or {
    "Farmers", "ItemShop", "Upgrade Tree", "Upgrades", "Rebirths",
    "Expand", "Sprinklers", "Fertilizer", "Fertilizers",
}
Hints.dataKeys = Hints.dataKeys or {
    "inventory", "farmers", "placed_farmers", "stats", "money",
    "discovered", "upgrade_tree", "sprinklers", "fertilizer",
}

local Result = {
    environment = {},
    networkCandidates = {},
    dataCandidates = {},
    moduleCandidates = {},
    configCandidates = {},
    plot = {},
    unresolved = {},
}
env.__DEOB_RUNTIME_PROBE_RESULT = Result

local lines = {}
local function out(s)
    s = tostring(s)
    table.insert(lines, s)
    print(s)
end

local function fullName(x)
    local ok, value = pcall(function() return x:GetFullName() end)
    return ok and value or tostring(x)
end

local function typeName(v)
    local ok, value = pcall(function() return typeof(v) end)
    return ok and value or type(v)
end

local function sortedKeys(t, maxCount)
    local keys = {}
    if type(t) ~= "table" then return keys end
    for k in next, t do
        table.insert(keys, tostring(k))
    end
    table.sort(keys)
    if maxCount and #keys > maxCount then
        local trimmed = {}
        for i = 1, maxCount do trimmed[i] = keys[i] end
        table.insert(trimmed, "…(+" .. tostring(#keys - maxCount) .. ")")
        return trimmed
    end
    return keys
end

local function keySet(t)
    local r = {}
    if type(t) == "table" then
        for k in next, t do r[tostring(k)] = true end
    end
    return r
end

local function interfaceScore(t)
    if type(t) ~= "table" then return 0, {} end
    local score, why = 0, {}
    local interesting = {
        FireServer = 8, InvokeServer = 8, FireServerUnreliable = 4,
        InvokeServerWithTimeout = 4, GetObject = 2, GetReference = 2,
        get = 2, Get = 2, Data = 5, Connect = 2, Initialize = 2,
    }
    for k, pts in pairs(interesting) do
        if t[k] ~= nil then
            score += pts
            table.insert(why, k .. "<" .. typeName(t[k]) .. ">")
        end
    end
    table.sort(why)
    return score, why
end

local loadedList = {}
local loadedSet = {}
if type(getloadedmodules) == "function" then
    local ok, mods = pcall(getloadedmodules)
    if ok and type(mods) == "table" then
        loadedList = mods
        for _, m in ipairs(mods) do loadedSet[m] = true end
    end
end

local function inspectLoadedModule(mod)
    if not loadedSet[mod] then return nil end
    local ok, value = pcall(require, mod)
    if not ok then
        return {path = fullName(mod), error = tostring(value), loaded = true}
    end
    local score, why = interfaceScore(value)
    return {
        path = fullName(mod),
        loaded = true,
        returnType = typeName(value),
        score = score,
        interface = why,
        keys = type(value) == "table" and sortedKeys(value, 35) or {},
        value = value,
    }
end

out("========== GENERIC DEOB RUNTIME PROBE ==========")
out("")
out("[ENVIRONMENT]")
Result.environment.PlaceId = game.PlaceId
Result.environment.GameId = game.GameId
Result.environment.PlaceVersion = game.PlaceVersion
Result.environment.Player = LocalPlayer and LocalPlayer.Name or "nil"
Result.environment.replicatedDescendants = #ReplicatedStorage:GetDescendants()
Result.environment.loadedModules = #loadedList
for k, v in pairs(Result.environment) do out(tostring(k) .. "=" .. tostring(v)) end
out("getloadedmodules=" .. tostring(type(getloadedmodules) == "function"))
out("getgc=" .. tostring(type(getgc) == "function"))
out("decompile=" .. tostring(type(decompile) == "function"))
out("Safety: read-only; no remotes fired/invoked; no hooks; no unloaded modules required.")

out("")
out("[LOADED MODULE CANDIDATES]")
local candidateRows = {}
for _, mod in ipairs(loadedList) do
    if typeof(mod) == "Instance" and mod:IsA("ModuleScript") then
        local lower = string.lower(mod.Name)
        local nameHit = false
        for _, hint in ipairs(Hints.moduleNames) do
            if string.find(lower, string.lower(hint), 1, true) then nameHit = true break end
        end
        if nameHit then
            local row = inspectLoadedModule(mod)
            if row then table.insert(candidateRows, row) end
        end
    end
end
-- Also score all already-loaded modules, but only retain strong interfaces.
for _, mod in ipairs(loadedList) do
    if typeof(mod) == "Instance" and mod:IsA("ModuleScript") then
        local already = false
        for _, r in ipairs(candidateRows) do if r.path == fullName(mod) then already = true break end end
        if not already then
            local row = inspectLoadedModule(mod)
            if row and (row.score or 0) >= 5 then table.insert(candidateRows, row) end
        end
    end
end
table.sort(candidateRows, function(a,b) return (a.score or 0) > (b.score or 0) end)
for i, row in ipairs(candidateRows) do
    local safe = {
        path=row.path, loaded=row.loaded, returnType=row.returnType,
        score=row.score, interface=row.interface, keys=row.keys, error=row.error,
    }
    table.insert(Result.moduleCandidates, safe)
    out(string.format("%d) %s score=%s return=%s", i, row.path, tostring(row.score), tostring(row.returnType)))
    if row.error then out("   error=" .. row.error) end
    if row.interface and #row.interface > 0 then out("   interface: " .. table.concat(row.interface, ", ")) end
    if row.keys and #row.keys > 0 then out("   keys: " .. table.concat(row.keys, ", ")) end

    if row.score and row.score >= 12 and row.interface then
        local ks = table.concat(row.interface, " ")
        if string.find(ks, "FireServer", 1, true) or string.find(ks, "InvokeServer", 1, true) then
            table.insert(Result.networkCandidates, safe)
        end
    end
    if row.value and type(row.value) == "table" and type(row.value.Data) == "table" then
        local dataRow = {path=row.path, keys=sortedKeys(row.value.Data, 80)}
        table.insert(Result.dataCandidates, dataRow)
    end
end

out("")
out("[NETWORK CANDIDATES]")
if #Result.networkCandidates == 0 then
    out("none confirmed from already-loaded module interfaces")
else
    for i,r in ipairs(Result.networkCandidates) do
        out(string.format("%d) %s [%s]", i, r.path, table.concat(r.interface or {}, ", ")))
    end
end

out("")
out("[DATA CANDIDATES]")
if #Result.dataCandidates == 0 then
    out("none confirmed from already-loaded modules")
else
    for i,r in ipairs(Result.dataCandidates) do
        out(string.format("%d) %s", i, r.path))
        out("   Data keys: " .. table.concat(r.keys or {}, ", "))
    end
end

out("")
out("[CONFIG CANDIDATES]")
local configNameSet = {}
for _, n in ipairs(Hints.configNames) do configNameSet[string.lower(n)] = true end
for _, inst in ipairs(ReplicatedStorage:GetDescendants()) do
    if inst:IsA("ModuleScript") and configNameSet[string.lower(inst.Name)] then
        local row = {name=inst.Name, path=fullName(inst), loaded=loadedSet[inst] == true}
        table.insert(Result.configCandidates, row)
        out(string.format("- %s -> %s loaded=%s", row.name, row.path, tostring(row.loaded)))
    end
end
if #Result.configCandidates == 0 then out("none by configured names") end

out("")
out("[LOCAL PLAYER PLOT]")
if LocalPlayer then
    local plotObj = LocalPlayer:FindFirstChild("Plot")
    if plotObj then
        Result.plot.path = fullName(plotObj)
        Result.plot.class = plotObj.ClassName
        out("path=" .. Result.plot.path .. " class=" .. Result.plot.class)
        if plotObj:IsA("ObjectValue") then
            Result.plot.valuePath = plotObj.Value and fullName(plotObj.Value) or "nil"
            out("Value=" .. Result.plot.valuePath)
            if plotObj.Value then
                Result.plot.children = {}
                out("children:")
                for _, child in ipairs(plotObj.Value:GetChildren()) do
                    table.insert(Result.plot.children, {name=child.Name, class=child.ClassName})
                end
                table.sort(Result.plot.children, function(a,b)
                    if a.name == b.name then return a.class < b.class end
                    return a.name < b.name
                end)
                for _, c in ipairs(Result.plot.children) do
                    out("   - " .. c.name .. " [" .. c.class .. "]")
                end
            end
        end
    else
        out("Players.LocalPlayer.Plot not found")
        table.insert(Result.unresolved, "LocalPlayer.Plot")
    end
end

out("")
out("[REMOTE INSTANCE SUMMARY]")
local ev, fn = 0, 0
for _, inst in ipairs(ReplicatedStorage:GetDescendants()) do
    if inst:IsA("RemoteEvent") then ev += 1 end
    if inst:IsA("RemoteFunction") then fn += 1 end
end
Result.remoteInstances = {RemoteEvent=ev, RemoteFunction=fn}
out("RemoteEvent=" .. ev .. " RemoteFunction=" .. fn)

out("")
out("[UNRESOLVED]")
if #Result.unresolved == 0 then out("none from generic checks") else
    for _, x in ipairs(Result.unresolved) do out("- " .. x) end
end

Result.report = table.concat(lines, "\n")
out("")
out("Result table: getgenv().__DEOB_RUNTIME_PROBE_RESULT")
out("========== END PROBE ==========")
