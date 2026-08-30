    -- Creating Ui
    if game.PlaceId == 9498006165 then
        local OrionLib = loadstring(game:HttpGet(('https://raw.githubusercontent.com/shlexware/Orion/main/source')))()
        local Window = OrionLib:MakeWindow({Name = "Toothpaste Hub | Tapping Simulator!", HidePremium = false,IntroText = "Toothpaste Hub", SaveConfig = true, ConfigFolder = "Toothpaste"})
        
        -- Values
        getgenv().autoTap = true
        getgenv().autoReb = true
        getgenv().selectReb = "1"
        getgenv().autoHatch = true
        getgenv().selectEgg = "Starter"
        getgenv().autoClaim = true
        getgenv().autoTapEvent = true
    
        -- Functions
        function autoTap()
            while getgenv().autoTap == true do
                game:GetService("ReplicatedStorage").Events.Tap:FireServer("Main")
                wait()
            end
        end
    
        function autoReb()
            while getgenv().autoReb == true do
                game:GetService("ReplicatedStorage").Events.Rebirth:FireServer(getgenv().selectReb)
                wait()
            end
        end
    
        function autoHatch()
            while getgenv().autoHatch == true do
                game:GetService("ReplicatedStorage").Events.HatchEgg:InvokeServer({},getgenv().selectEgg,1)
                wait()
            end
        end

        function autoClaimReward()
            while getgenv().autoClaim == true do
                game:GetService("ReplicatedStorage").Events.ClaimRandomReward:FireServer()
                wait()
            end
        end

        function autoTapEvent()
            while getgenv().autoTapEvent == true do
                game:GetService("ReplicatedStorage").Events.Tap:FireServer("Events")
                wait()
            end
        end    

        -- Creating Tab
        local FarmTab = Window:MakeTab({
            Name = "AutoFarm",
            Icon = "rbxassetid://4483345998",
            PremiumOnly = false
        })
    
        local EggsTab = Window:MakeTab({
            Name = "Auto Hatch",
            Icon = "rbxassetid://4483345998",
            PremiumOnly = false
        })

        local MiscTab = Window:MakeTab({
            Name = "Misc",
            Icon = "rbxassetid://4483345998",
            PremiumOnly = false
        })
       
        -- Coding for Farm Tab
        FarmTab:AddToggle({
            Name = "Auto Tap",
            Default = false,
            Callback = function(Value)
                getgenv().autoTap = Value
                autoTap()
            end    
        })

        FarmTab:AddToggle({
            Name = "Auto Tap Event",
            Default = false,
            Callback = function(Value)
                getgenv().autoTapEvent = Value
                autoTapEvent()
            end    
        })

        FarmTab:AddToggle({
            Name = "Auto Claim Random Reward",
            Default = false,
            Callback = function(Value)
                getgenv().autoClaim = Value
                autoClaimReward()
            end    
        })
    
        FarmTab:AddToggle({
            Name = "Auto Rebirth",
            Default = false,
            Callback = function(Value)
                getgenv().autoReb = Value
                autoReb()
            end    
        })
    
        EggsTab:AddToggle({
            Name = "Auto Hactch",
            Default = false,
            Callback = function(Value)
                getgenv().autoHatch = Value
                autoHatch()
            end    
        })
        
        -- Coding for dropdowns
        FarmTab:AddDropdown({
            Name = "Select Rebirth",
            Default = "1",
            Options = {"1", "5", "10", "20", "100", "500", "4000", "13500", "32000", "62500", "108000", "171500", "256000", "364500", "500000", "1000000", "2000000", "100000000", "1000000000", "10000000000", "1000000000000"},
            Callback = function(Value)
                getgenv().selectReb = Value
                print(getgenv().selectReb)
            end    
        })
    
        local eggs = {}
        local shops = game:GetService("Workspace").Shops
    
        for i,v in ipairs(shops:GetChildren()) do
            table.insert(eggs,v.Name)
        end
    
        EggsTab:AddDropdown({
            Name = "Select Egg";
            Default = "Starter";
            Options = eggs;
            Callback = function(Value)
                getgenv().selectEgg = Value
                print(getgenv().selectEgg)
            end    
        })
           
        -- Coding for slider
    
        MiscTab:AddSlider({
            Name = "WalkSpeed",
            Min = 0,
            Max = 500,
            Default = 16,
            Color = Color3.fromRGB(255,255,255),
            Increment = 1,
            ValueName = " ",
            Callback = function(Value)
                game.Players.LocalPlayer.Character.Humanoid.WalkSpeed = Value
            end    
        })
        
        MiscTab:AddSlider({
            Name = "JumpPower",
            Min = 0,
            Max = 500,
            Default = 50,
            Color = Color3.fromRGB(255,255,255),
            Increment = 1,
            ValueName = " ",
            Callback = function(Value)
                game.Players.LocalPlayer.Character.Humanoid.JumpPower = Value
            end    
        })
    
    end
    OrionLib:Init()
