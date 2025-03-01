# ExtractArkItems

## Python script is to find the dino ids or item id etc from installed mods' UFSFiles at given path
    Currently only worked with ARK SA - but with some creativity can be applied to wider verity of files/games

### Format of the data processed for each line:
    <some categorization data to ignore=-LineSearchStart><what we are looking for=-LineSearch><extention=-LineSearchExt><rest of the data ignored>  
    eg: `ShooterGame/Mods/ArkDescended/Content/Dinos/Daeodon/Excellent/Daeodon_Character_BP_Excellent.uasset	xxxx-xx-xxTxx:xx:xx.xxxZ`  

### Do Check help of the script to see available arguments and options avaialble:

> `extractArkItems.py -help`


### Example Commands:

1. To extract list of dinos paths that can be used to summon or GMSummon commands eg. ARK descended mod
>`extractArkItems.py -LineSearchStart="ShooterGame/Mods/ArkDescended/Content/Dinos/.*/" -LineSearch=(.+Character_BP_.+)`

2. To extract Varients from shiny mod 
>`extractArkItems.py -LineSearchStart="ShooterGame/Mods/ShinyAscended/Content/Data/Variants/.*_"`

3. To extract base colors from shiny mod
>`extractArkItems.py -LineSearchStart="ShooterGame/Mods/ShinyAscended/Content/Data/ColorSets/[^/]*_"`

4. To extract event colors from shiny mod
>`extractArkItems.py -LineSearchStart="ShooterGame/Mods/ShinyAscended/Content/Data/ColorSets/Events/.*_`
 
> All of these ran from `<steam_path>\steamapps\common\ARK Survival Ascended`, if not, need to give it as -directory.


### Notes:

> Though we can use single regex as input but made 3 parts because we can fix the common ones inside the script itself and change only when required thorugh arguments.
