"""
update_to_v6.py  -  upgrades your Exam Buddy folder from version 5 to version 6, IN PLACE.

How to use (run it ONCE):
  1. Copy this file into your exam_buddy folder, next to main.py.
  2. In the VS Code terminal, inside that folder, run:    python update_to_v6.py

What is new in version 6:
  - Applications page: pick your exam from a list (JEE, NEET, NDA, SSC, BITSAT, VITEEE, state exams ...)
    and see the documents that exam needs. The documents page shows a tick-list for that exam.
  - Overview page: a new "Completed" box that shows the names of your completed exams.
  - The useless "Documents" link is hidden for the admin.
What it does: saves a backup of every file it changes, writes static/app.js, static/styles.css,
static/exams.js, and makes 4 small edits in static/index.html. It checks everything and puts your
old files back if something is wrong. It NEVER touches your database or uploads.
"""
import base64
import hashlib
import shutil
import sys
import zlib
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent

FILES = {
    "static/app.js": (
        "f92e67169ae743374a09da8036ab973464d5d6dd9f92812bb791d24518f364d8",
        "eNrNPduO20h27/6KMtewxVhN2d7ZYNIXDTzt9tizvsFtbxAojW6KLLU4pkguSbmt7RWwD0leEiBANgiQYIMkQJAfyMO+76fMF+QT"
        "cs6pC6t4k9Qe7OwA45bIqlOnTp069yoFaVKU7PGb5+yIOc7BrZiXrEw/8AS+F7woojQ5LdPcv+TeJS+fl3wxcPj0nJo4Lvv1r3Wv"
        "YJnnPCnfFzyHvskyjq3nb/J0FsUcXl2vxQt/Wc5fpiE+cuL0Mkr08H5RvosWPD+4dcsvVknAZsskKAEV5mfRIPPL+ZClGT4oCJ7L"
        "rm8xFtBU5twPeY7PE37FnolvA9naU28Bb+h2AL2iGRvQbFzV1St4OXAeA3ZpHv3Kx47OkDlfcz+HqTnsviCQ7q1gT9Nwxe7eZbft"
        "JxFg5ScBT2fsaZovnvil71IzNdzcLwbOcZqUQKW9d6uMO66YELMxspoAQn6WxVFA+I2+KwBJwmitKZHzIoMPSF//yo9KNuNlMB/g"
        "Wt9ngojXnudJZIdqMEEWXIgQUJXrxViZr9i1eiTgqQE8HH3gHrA1A3SCORucwwTWkjy3dbP0g5oXPtePgTzlEhbs6Ih98eAhkkau"
        "h2jLND8Cp9V5MueL9COvs+UBdVzTv+U8T6+IF07yPM0HOAMv5KUfxcS9p+mCl/MouWRXQFx2lafJpcfexNwHyuGk/Us/SryKuDkv"
        "l3lClDi4tb6lWZMXgZ/xZ+UiHnz04yUX+MvWp2UOQ4gX7KuvYCou4J7FfsAHo8ndw7Fz72x0OWQBOxqzwbVz19l37vqL7MAZOof4"
        "OS7x4xg/XuLHe849+PjLZUrP7+Hzn/z0Lw6c9SQ4c10LsWKeXr1O4tUgCgVOE2cOk977GPEr6IvbUH0O/WI+Tf08FA/OvFman/jA"
        "NJ8QrzANlgsgEkqCk5jjx69Xz8PBJ9cLYr8oXkRF6ZXp5WXMB848CkOOG+cTuw0rC2MTBbtgOEVU8r1ZmpY8d3rhRSGxSh3XfuiJ"
        "/3EvjpIPxUbYiKxBn36wZZrt+UTl4qZI1xbqGYw8gGWqVs1Chl1FSZheeUWQp3H8Lh1cAwr7D4ZTPvc/Rmm+7xQLoOHcWeN2rECn"
        "GU9Qog0WIHAFFxjiFx/iPKsxK6boJwC147ixYP4l/1RKISW1yaaewF4L2gko4GgkIbqi4i2/BEKSKlkQkki9XD50Nqw10Cv2pzzu"
        "X5Pb1ShbTBKhEqq/XEY5h+U0kNzcu4zKmDdIZEwTRMJxzv2Ss1W6zJkfBOkyKR22z5y/5HEALMCmfvBhC5oWy+k2o52Wfl6yNL/0"
        "k6hA8Ufj8k/+gmUgmfycFItHGJwk2IkaCMlZgEzGpSqjZMm97ZBaRCWgFCUJz5+9e/mia/py5uywyPxk/P3f/dPhiD4RIi/SS9Cn"
        "zXe9CJBtsVf601Z2wO37ke/CDooLN4PcicEyAHOV5iGAhO8pLHkGSpg36ASqrGqLRJEGVvUQx9pBToAIqllZYrVIXvCPAFoIDPro"
        "AXPg3yd85i9ja9OSGAB0txIWVbfpsizTZGM/xUHYkWC0ihsBzAujwp/GtEvLfMm1/aKNj0r4WXKlsjmEhYPmpjOCf0fYYaTbgeWE"
        "VkMa7jtvXp++g+9o6u1/e/r6FZgzqOqj2WqgYDGGwmN/K/lCFoIHIBYDd6j78wVsug0AqE0nBMUc+1szIcGR/dfuWhpVrNVsF292"
        "A63XbHPXdnnmPJaiIiDJEW4JrFM+Oq/AUIyFhLmKyrkQeGg5SpnkbR6hQ/f4YagVj7sdmk19M/Pjgm/s3C7tCAEplzYj0CnhhLm9"
        "A6Ru4d8ry4nnaZPT2K+AFtgFzQUpQOxWRbmKuRekMQkg5yePHn755z/jtUb93ANCLwjAuZiB47rSDoBgB7Xwa8ZhCbSMEPLLcolq"
        "AkPsj12lxZ/Sble+F7lN9OWg5unTm2UhrCD8r+aiFY2wwdBwoCtZy9HIeKLs44HhxGm3Ei3X9hUHz7Btkbm3AGQAiwMCNIsSH1YX"
        "gDT1hNhd0KyhDeuI0fpX6qSXCxZ6k3QRrRkfoXeZ/EqBCgGhss7bXB9tOidRGcFcANDAGNNDeSIcXhR8xC9eAfEDPngwfAhP0vdZ"
        "xvNjYHpF+k7eQbz3/I+AZtPqV8NvACFiDZ8JpIhCPvVzJSptGPW5bwkLzKV+WNhAWA1+uIDNjSbZY/wE8hFsZhBNaJOdlssQ+yo7"
        "fsPoBArm8bHfY2ngcbvCY9OiwYviBiMcNUYQLI7MWO0JB7RCXvGivWF3D98YnnDrjgSxmi5LcyeaYbwuSQxdGqJ43Ra1MhFuiWre"
        "YBIwBbE7M+jwkouwGoykyLY/cV4rCg6dxywA7ZMz/MogbCjtkE9A9ZJnheecoaSXEgK6vlypL9D555xnosfUL6JAO2zAiUvgTy57"
        "Kz4poP8T9Rm6v8/i1A+HyjHkQ+YnIUSxCBcCi+MoHIwQJAJ6bHwFWG/Ij+QEAfZG8EH6tlUrBowYifCohFgssyzNSwD2jMcZu6se"
        "IFmKD8xnv1zyQoQ0chbMuQKKdhK80IghxyJG+BeonoBBNnRe+gnQnyxYCO0WHCcWgP4rCEU5Uh2UJKBJJ0BLPtUUk96xboEABXrl"
        "nOtFuOIAHRrP8nSBLxYwxi0Q73X/y9pcyDOC1SmcanCkq8KLOrwjLXLb3YTp5KtTHvMAOPZxHA8cDzXIHgIGcaBifDzGIB+Pu+zW"
        "fh8Wge05FFkGdL9qMRpN+7cPNxTFFKyboCYkLM/60Ww43vAW+4Lp4WF3kmL0ARTgQD9x1CJizLlPtuL7NpCOXm+gjuHSLsQOV5t9"
        "QlPAsdUTT238XpLSIrX7KjjC5MHZ5u6d3g5BeEgQYGH4O0y6CM1ve8rVZCsZL0Us8r0SW8posLsoseSi1IilidPe1CClAV5vufZO"
        "pvxB5x32QwJ2xQlEsd5EwQeeowKpoJnySaiWFjwkT1hYiGftOCgBZXY4Fc86kBbaVLsR+LZXszdyGLbBgaIdNBJTrqLn1Cxrmjr2"
        "aDGqhYpGgSM4QFvMQ4qcSCLtFk2y5JgAq4FGBU3hiMxtM2+H27ov0A5QZPAnbnCyNPEtmVCTOkPHCDwhxSUibovAM0NUqIgxF4n2"
        "RpWYFPtEf6VcaamagV3SK0eH7GcPHjywKWVsQcyybSBDZ2SBtZhK5h416D1Bg3CIyrg4044L7NAF6EUPvKTBpLKgjL05NOwqa/Od"
        "9auHKxHEbrfVL8wQ95Ddua4b714BQ0EKlDkuSL317YvesUC05VGwZ2BdGw+n7sU8uSzn2wBCGjVg4MMdYICCDsHRbwcDUhFczIGP"
        "fHN7AoleEfoNgWuP0TaKwUWFZFyUBDG4FcXAlzlT1zUwkH5omvA2sL6ZZjVGcLdBPqiaNyiZ8AYOuGLof04gu4xC6xSSO9Rw4WcK"
        "G0w0nGND1z3bCQXioOZy0FOJCbhk4ut3Kcg8TJW76JO9SkV6Q4NiK146uy0eWuGyxWk0BSPlsoaH3P1maACNsxo1PnfVewjJTJuw"
        "Igh9q9OjRApU9CBarN2BLZoszU0T67YBRTMrlt3iiquqkS0gWWGuGih6twOsbA482IQl5+bR6x3ABVG56oaGb3cAFqbTblhgd/Lz"
        "dHY+jXJYSwm0mbTxP3K1TltlbSo7r+4xa2+ycpbfQ9iyL2pJ1NvfbQ1qYUsk2f5OZK8BsOi0vwvNb9lhz2bJ0udM7+bzuvmEjJCh"
        "MCscNRlkk1qw2wradBuE2h5ssN4yM231XXKGKuTZE7WiF3vCjfAo+CAdH5117AMgUDOzjvCxNXVIzjXCV161ekh7sIh+xdmYffln"
        "Dx88+oL+kbHoOqynOCP+KeAcwgpfspdfQ/JAATSKs3TWU1BIpEiwlACGHIiX7lbZTElHyIzIkjdVZIYODj72QNmA/ho4YkvTDA82"
        "R64r62lYy16QGEDI600xxzSAFBKQxxBtovxKdYB3EBcC1XOOzSp5yTYuaLNyhPW5jRU/EwKSpZt831zQzhRC7zp1ZxNq6BkWOVql"
        "vQth5trjrXZNHCmvibjbsHtpsrGVkeOLrFxBWUgJXhPYSlUsC80kHefyWckxzbBAfxaczzdPnmIxCKAA0UkoKRH+p8XxtXEIC7Rg"
        "QrRgLg6hUwR+FiOn5sgRIbm9AEJfzvgwjD7WXhSrxTSNnfH3//LfhyN43dYGLIMEOoOagmq+8Z1rozYv9CD0d4mrKKymNeQdRbPD"
        "rN4S98p5CeWWdnrEXbM//B68lJdQQ+kFPMKmKB/OpyugzYiEw5r9/OvDUdaKHEQTHBgKN+sTpHboyRzkuV9iJuZFGvgxlyWDarCw"
        "vlkg7/D6+C2jz/oV+/43/6yitSoeIBMSKXw8YLpLAtYfpF+iGFnWWUtSdhFUFbmND6Xgkq+nZcLg/z3we8EY5vS5WDgsBaMVAjBH"
        "DmLyOsgHOIEoXLvO+BeIG6JwOBKwdoYZcjRXtbqpQD+hFxVcOSfJYOMLV1rATlvRi8JUVUmKvMLWW1O1VAwOggIqI4/GnwA38LkA"
        "Kon222FLOEdNhRZlBgkjsYd2kqttshR2sV5vvdaoFACFqCDli9qpPRgLkVgcR8TOXRn7eZ6UKS7g4Lqj4pDd3IqoLataBxH0TpNZ"
        "lEOCRSyxwF/hLcLpFICPceswjP+xr5chVF9DevsD1BUE/Cusqq4Uu7W6R9XCXtgLO7pzDax1UanAJycvTt6d0GTb1Y2paio983mU"
        "CdJshaxpagta1KPteaSatMAbUoHRJYYPIZgUZZRp8K5yKMJ9B50G2NOai4OPEZFICvhqQue9ISsDj4I4a2ByNv/EA3B8Fz4aKDhN"
        "p3NUZASNKgNhDJEqTMOxK7+ouFvi1iQhSVgjALyrjySofuUnJQ/76I7+eFsxF8n1KzvDLrMFUcLbCkis8JrZoRDlMNhPiBkZCsC8"
        "/LmsNDYdZXgECQwjVGDjQu3lxPBcwk6hiCrAjVjZrO38VbpkfowZrxUDaQGZN5lwq2QQ4uSx12ChYg1qVNL6YbBCxdwRrEfS0zQp"
        "WD+5Wk3WDs9VU2V/5zUdmiBkVngDFNmqAxDIf15swgPb1PrX/NftJ3LkOAdsJ4y36GFheLTRoqc+qDPrFWL1ji25QupLpmJvglAl"
        "AzJMCoWO23AY6pkhg4mNV4p7pbkGVWI5Jl7utSSG76FRvGxLDd/A3a5iPLTrjnFeA7kDKelFAT/xwN7b6pAJUYvBdt5z7IMBotNr"
        "cQZIpaGsoysTChSeCtseIDxPME1wiTOHb6/Izz1OoV8gTko5b2m/4w5/y2VFQ5dAQS+gOBpfHIpDSGDmFiCMJBZfOUJhQMt9x1mD"
        "xVyAmSpabrDlmktqaE4Mvm4lb7dxtYxedW/LyBBs9rb8Bpcpv0vVxSvm86fAyshd5G6Jwgpdv2+V7ve7YYQeBZJxAW7qhP3utzdx"
        "wsyw9frOtfwqJQ16NujzOPebPWQTFxmi03HzPZJAygQWXyBRRpbLutcre5+FVAxqeGegV8XDdu9sa8cJq1vVS7Hr9jIIrSPPG7ta"
        "a9a1U5+UeiELZTu8pgwUgg9WS8NrMpUqkly6TE3RdUP/CQOLpn2l7Hdps8jsU+dOupA0EQZ3h9FaWejmbm0Y6W8evzt+1qH1xTCk"
        "K3eX/3IWkiFqdvANDHsR9lPVAp8ZtdeVUjsYP4DAdyBiu00OCXRPNuywW+RMN4ORDW9ovnQg02+SdAyt7ZK2qg1z/U/tsjCmQrXh"
        "58fNrUGNzaIq0Fq0lK422VZBqenXlJMucttWQdWr47AgL1lpqoD2kZSBYhGQahh0hhLGOc/5JkWkUdHWwE2V0b/+102UUeFJfuqJ"
        "BRbalV9vG9Ur+qN6lt7YTjcUXbqhaOiGLpldFbVXq0v1YUMKKBjW5IU5R2q9h4PwDiISEIOA9ksELWd80VGkIguUzAqVYrlAVTZE"
        "v7YYor0ylFy4sWKFKqdGEoBdtUJvCGRPNcuwZcdtqHARNdyiYqDuykxI0kxUWThsHokaLJx4cjasl8+qFiZi2OqNLEbQDWR1wnm9"
        "ITrVVfmsao1mwLl8eq623hngJ6zxwYROLw2TMxd3osED5vykOQOrTK012+nFT4ytJJbd5MONVJTLY9GQnlUFDReHJcZ7xoclniWA"
        "Pzl+HONRocMRfMAvJ1ghoL+9hbo6/cWktX74LWDIQ/F1hABHCjjqUJiWwAHptETq0JihzetLT6UVyrDtLVUtdL/G4j/r7dJkgHM6"
        "TWC+1uJm2Spu8JUhcrAbTsxYDXxKs4O/RNALSBfUZL9YjqE6MlW0ivjKv8IlfCycrA3r3PS5dOemr6KX/k/GcxGZmZqRTvv5vDpu"
        "Ix44bp+/onoZJS2t0C03Sbo36muR8SCaRRje2KSjNvhKzi5eDbnocL+BEhDajCcPA0ezQwyWH0Odd87/0ECnNXejcmmED7cpu7Sj"
        "n0RZKx3D2cZFam6jFh8fNpU6KqS8/o69tWEnaS1l7Rv5tNo66sGPb2o1uLu40d7Z3jBrHcracD+wK7+DuWbsIu3jqH1UiH1khMhk"
        "d4iUkY536oEyfKgDZe39zCBevbvxbgOUt7xIYygnaoBQL6r+n73XlZ8kCdKyz7feis+TafoJKtFFdTduwZpv074HG2ZrqxzaNexR"
        "k5o/SvBDng34Y0U9Gmu6c6iovke2o5r0CaivINtXkpdheyYB3Gnw/u1zDFVDER8koNUmbdB2M/XqMYObk240Ynuf+R/79uTEqOa5"
        "r+pDIKPPeWLe0QaL/jzUl7eJ1Xjy+vj83fN3L05O5ZlF3w/nvp/j4TrxiZG2GDpPQUDD6sFJBvP6BJDlQ6rMxJOMooIVz8Zd0kEd"
        "ecSOhMHDBwCSJCd7+ICBbv5QzLmIgNNpSKithKC3rDgCWHiuDusXq6YWtEcVtEc3hYZH82ABTsXZYGYclNwXVd0DPIRIZrdLEKRa"
        "uVcQzV+CIrRPO+IpQ1hvaiuTQ2IVvPoeQfDfclVx3XpEyDpMpHJA9rFc4+BuPZO9dRZE3AX3HTeOFVQpZ20MC2zUrB2RcO5OSBt5"
        "49sA2lXwe5O6212jUOVzK3SGdorWgQci1QrKSocdTcMP0FFY7nBQqnbhlgJG4q2+x6LwoL5a+ugZwmorT8LaUjhJETwP2y8h6Ljx"
        "r1nTQjDWIywAugCyypv/9q+tSw/39ZWH9+lM83ptrpp1q1+jouk4XcYhlTPRPqHdFcXcswsZpnE6bd4miE9VhYQ8eIZABu/fvpA+"
        "7muyIeH7ANvCgSrnfBr7yQdn9wVrK7X5BeoRCloNGcU3jEIkFSUzhD2kR+n+QLoSK1th2s5z9CBm4HPn+ptakY2s/DFVoyCI1I5w"
        "QAz6wZr5yEOlLg7Dp0aEHLeNrAo+nkdxOCip9bblOTqdLhGsSHGh4kGqUOjCDjoihKcRhxFV5ey1QXBZRYtHxhOl7+slaVGSLWFV"
        "BKoqlD/UBbjygK5YNNpFIL5hAlOwLQvrJDaVjEHQ0FCMUYIaAYxQDJWzgdJuUHdWwJDQOWFKodhfH7ArNBKhegW0xwcYqODAx65X"
        "TXy6BDKfiggc1JMDBQrT4sGyBDw79IGv8OR9iCe78RARJdEHatVBS8l3ihM+YicBblKeyUtNJwDl7IC49aPWC5OPgPIZ3nWgs/p4"
        "DsjBR+bhsUBetXOttLxS8ng3hNTSWknrZ4/0s0ckaiEnve+c4B99Tt4YBURFYcREcUToBaejkAziCiX4PnF8NbIjR9afHjln7tlQ"
        "9n9i2hYmIDwOsQOcb8giMQFcqicVDKP9U6j+5Tmo+qQ2gRm9ONfzUGNV4xtQXqYdUBbpDlAUrybLxdSeg0T8XL9pncvLdEqHA6p+"
        "4iQLNqflNBsfA8EvUwirG82D6llLj8dhKMpFDLz0o7YR8CyMCV18b2lJHp3ZtJAPWtq+icjGt2apHxntMRZeceuVn2NpGnEsPTb2"
        "5IQ2LEmbM2TByURyr2BqDMITE9Z49OzMtdR2wcUBwX5OpZhNiXJhAuJIBnXbd78MaFQ3zP51cR9ul8Xjs1U1olHQfuaqw4h0z+sn"
        "uBfAUPXq0CKiSUhUjVx1LuahqwnlZctibqgCLNSNZjOei/tw8hTkhF0Rtc8uwCuxwV+QkYJknHyC8z5nayDQnWscdK0dezrIeJ85"
        "+rYuunDDuKoXDdc5RFzwiLEZ0JG5EBXmmn8xhqKkMCIvRSkIPPaDZznwLsYF2EMBHvtwD0fQ+DBTgBZLLBaBWzBXzliqmdCoRq5q"
        "vhjYvaCIwDoAHQPXblFBj1DPpHZQNaWzWRTAtUfi1A5Gs+iYM03g/lFFX6TRlTg6oRExbkYbf/9v/2lH1q5EbKyWglFwURxbqR8m"
        "lWoBUwj4mSuGaiEf9KwHw+QbcQNeMz3U0pQGw6bybuSWe5Th+MJhNNa18WhgHY6isVPBXaAmN9eE4s6EP1YT0Yrg3SSKpeTUEDJB"
        "wf7bhqboUhKa15FjkVlYHWvZQhYZWC3EfNZGeMswN6EaVhswcgWsZwI88lm2qgW9aisrVbxYYFg6mXdtsXatyy0MgwTjY33ni0SX"
        "PTQkjZoC08NBIwWgbFvypsOHQ5G2RDNMXZLDzFwdXaHSqCjoOMnWGi0zsVyP5FQurMuHxa1B/fd+9V+9IgnUfvUKHUEzsDK8aJBm"
        "dIQnbLlq6KAlQoaQ5NkIkDzA6pDWYlh2XT0EChZarIn7fI/pYiKoLQJ/RF6FDrwFHhzddS6qOXKmzklpZKTVm1HR67EYQFyNaAna"
        "rLETFUW/0iF9MHgqDLXIpbuRUrjiziU8zZC5DphLqShLX/CgxxEeygvxzMegm7LG+iZQsko1/CICg9fpF0/VzfDdnZHF8YmrJacl"
        "FOl+NeB4oU+qsjo0FywhQBXvKkcMTUnR0Yqg36GbDO2jkjj3VrXzvljCEpHLgpTz2LG+dUorFBCdkBmUWw0RggEg3ZAv8SYvSpso"
        "EVGpBctlIVSk31JdoEKLWpEDddBTVJr5Gzwz1KSnDKiYTg3QngynDaaPtE7I+hHLV51FKF3XNqcmsqAFnHIqFKkimBMc78w6/JoG"
        "9UOpMsBFhxNDfEonAGnr4wcrgEFyWm9EZYvhIObFjV38slfEaSn45c41Ib3usS/uXOOEqh0gVgHAmAyZjf/vP377NzbDQZP6mUd2"
        "k2N8FH0ibpUJGJLUGNYx1JGF3O0Gj1gkiBIczMirkXdPVD4Sp5UpI0Zn24FA8BhUJ152lJVHjpcll0Pvu4z+4fDvFZ9mQy8LZ87O"
        "KV8hCE5hNQb35ED3XEfsTBRab4UdTbJTHINFq8FWwbUlUQWWxsSllJNIoUogeUERMrBhxFYbn+ijnHTCa4BBaTA71etDFeEh0hAQ"
        "TRq05I6cLx26Yw6FASO052kMbuwRqtxSHKfC2NzUvopOHwccN3in7ZA2lY1ITMa9a7ojo6FBBMKTgmDmWpDtzC3aVCtg2pXmlsHD"
        "jwG8wqgMHJcCJQLRGY89jq/8VSGv52tVeZ6uo5MZYbF2apU7tjQZ4Zd5BDoPHZpKJpyHfCblAlnaM5At+q7ei0Oy7Gy6z6S5t7bg"
        "IyxpdYutQpYmrBHamZIJ6BE4gfho5sEHeNZpixYTaqIcRmi68D+JYoEj5+GDBw6zlLfiK0cYznpxxY4VX5wb2896zjV2EBFDZNF2"
        "6/dwJAh4IUlq5H1N67f6SZhq8ap3a0P1EZudivMspMWGyiasbN1+yUacsOUeMGaLJfTKHBcXpDljzJOyMPdn5ZYVLR3wKByN9COr"
        "S9tcVAbVlGR10x1nSQ7ED5GP5GZkEG+MxFzcqIguEzDyci4Tj0+fvzixM4/UDtJ6b2DaIv+LwQd6qvJ6QyyjQSsbb4ZeqjTf4Ns3"
        "31Cu79U3rrpnVI0G8E7VZywFUJ+Biig+8S74OUTlwe+AcEkdEiYIzYuS+AtY0EoBqJ8KIi1y8aNqZqzqu+gUlCqFIRShuBlLycAL"
        "u264e28Y/mObXST0SGUXdQVnbMPIiiL3WEcvU+UO4N6D4z5wWaw4ZMrVJbbwEX7NCVaW0lJJI0RjiToScega0DWteFE9Ngc3deY5"
        "jUojU/CbNrQwgWnepAJw8pMzV+sAy2xVyZoWwWyanPirK+CLotejfrpLyj2siZWFRJVeEFHNVq1gzVfdXaJEOzZTP2OG6KYiCiTL"
        "gNoUSuoSzJQsZRXMqeqCNNyU5oRObjBPU3BN4aPTerCvqhBUoh15uK75embYG4MxNN1PN2q6C+tqtRupbIg8iKVb/4mpTXHrW2ts"
        "8MIsibvodN6UCNZCteaybe9o7+DWGfrhB/TrfnBfDRooJ4YsY2Wo4Q4zFcb6x/adfky3qcsiMyKZBx3JeuUs0BpuH8Ikz4l+y1Gt"
        "PREde4F4wr+e+hU/6z4KkeiFdF1a80ZU+v+zU//V0FZJWc0v7L6JA/vf4KaNPvhNyhtLXyf8pivdiCWhpAS7Wfe5GRewWTQ/FmrC"
        "F5ApHd9B5A23tRkwW25pa4VodMFj7fqctZrd97/5H+E8o5uJ7iWiibV1UDKchOqs/3a3tVGDlhvbmLiyzX6l5BeiTRxsvzbPjIBZ"
        "MrSqj3a8/q297Mq8AI5+fEEJU6kNcBtVzyrNUIVGejmEpJven5YvosUmVHDu1y6Ui+inCwyLut7Aeln9zE3P/XDVz/603gje2XXX"
        "W7abm8x033S03N5qaFjrn2jtuSjjJ2bKhk2U9WTeqy8UiDZKVWaZHuskFPaBlaUf3a29InMVf7sFH5qne4V9oXZ4FfbHu2b0vU7P"
        "0M3FQ6QUlYG3VnaiPy9RtN3t1MfiW+SFxOwvTOZ/31lyKBoPq5RGVVS4E8vszDA/hDc+o1p3TLmRvUmyaUA5LpGKMRzcWoDfl4m+"
        "W6z10KiVZRfWCPpJlFfPhSn1tG3sb9IUfs2BJGMhEu5EyXZL6w3l0qm+EDvjz0ZAgI9NMRYK/rqoH6QQa4E+37tnz0/pwuMl/pqi"
        "9AqNst1mUgodRpRBIf4OmEitVdkz4TUjGJEUOxUnoLWryJRjDRpCnxuHJaRraDCOoB1uq8yAcjJi0ptNPk3YZR5rL+ISXQ47/Dsv"
        "y6zYH43odrpLojGkDhcj8pdH4YiPoCxmhOEEulvzRuemcM3w0BTtIR2HwIWhHzMmXqtZgGKa5Iro0DitrGXREs0pWl5NN9GL5YwZ"
        "cRLeloBCxlhTuHeqIIffSohGeRVSEF7QZmrvGJfBqT5GsWXSg7Ake4F+DoLEGhss0bqZIUMSFyG/vML6zxtfkIg3dH4tdsAARn2H"
        "RxDkjrgxzCAGI4zWF91J/CIWVuyw1kVFaurlglokPJ82rnmURmhJ/HYHDvGW2g5yU9fFERY7gpG8UEfVKSARRzAT2xHHNtoXH03H"
        "lFAH/wQ6wXfo0P/rASa2luFxS0Trs8aAuUe/qkyD3bmGC2TRPUQHaJ+KTqyW4py8KjyRuxxkG5xH/VuGnUXZkTyxt2ayCuluMi2y"
        "gz/8XvxlosQn95ZJATaVboypUVKigxXcsARyL0q0aHQbMH739wQj5rNSQ8Av5OMDFAO9ZVydhatuk8AshwiLKKwxUhThwsTRIBrW"
        "Ao7ph1pyKZJ+jqrjuXDN0L2ELKfYCxlLoxqwIYQDP0vfD5zmXgPdBsSt5xSWcY15kcSnVKQwQG+154dONjimFvspown6uI2YvFFp"
        "gbErGo6qnapaMOQzUYUB3j/9ZCLuxkREzvcffpF9olgFIKzCD43DWvmSpPpjEfHNoLZVGEFYdF2s3olyeBEYUgRwvv/H/61zvm4M"
        "pkv7f2DLQIJuRWpaHIqB0kO8pBbCePBbN6RGM/i99WXman+6ITIqG09gus2JEXwG9lrzaJY1pX//h/qUtE1GRYiH03wsroMD8VCT"
        "uOPq0i6MQdGeDPylCkzHaQp5yJIewzkGrN7A2y3RxJX2C+7IXLrmhqfacrbOEv2tC4O4IS2hZh0rjIG+NWMJXVm6Wwyd2wEVta/E"
        "MQ76UTMS/dMVVLujieMaHq5xBW7jIA+dvUNURqTKW3+Iz8IUxGGN3tV1qp+xVN2ndUi3GSatmAwYVRt3KxpebsPloXAGvKpFHloM"
        "1t6Yhr3/GtREzJGYtsO/z2giQ0R/iMcc0qtzw17a3zQhw7SCHxsSHtkaym3VPZ0KfeSQBv8Yh2c9p/lbIsIoMn2H/hlin54Z/nCT"
        "Q+NMTQ7NM5hc67FfwxJqXhS9gfexayvvd9wavJM3KA9LQWn9CV4bhjdfclAXcGny65ey+vAFeRuAgZhT9WM1jd/PbPs5XgqDWD9r"
        "6R7c+n/uQB45"
    ),
    "static/styles.css": (
        "188780305e393adce4e8c09f5bf2fb2dffab5bd14f0f35857d4169fa2843ab35",
        "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"
        "1ea789vamzVo/PDjX4I6fzY="
    ),
    "static/exams.js": (
        "aad90371f06d056bc782075aaaf016aa584a44a6388f5e029aa472547a2793f4",
        "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"
    ),
}

# (old text, new text) edits for static/index.html. Skipped if the edit is already there.
INDEX_EDITS = [
    ('<script src="/static/app.js"></script>',
     '<script src="/static/exams.js"></script>\n  <script src="/static/app.js"></script>'),
    ('<button class="side-link" data-page="documents" onclick="openJee()">',
     '<button id="docs-nav" class="side-link" data-page="documents" onclick="openJee()">'),
    ('<small>Not yet completed</small></div></div>',
     '<small>Not yet completed</small></div><div class="metric-card"><span class="metric-icon mint">\u2605</span><span class="metric-label">Completed</span><strong id="metric-completed">0</strong><small id="metric-completed-names">No exam completed yet</small></div></div>'),
    ('<div class="panel-heading"><div><h3>Application assistance</h3><p>Create a preparation record and track your progress.</p></div></div><form',
     '<div class="panel-heading"><div><h3>Application assistance</h3><p>Pick your exam to see the documents you need, then create your record.</p></div></div><div id="exam-picker"></div><form'),
]
ALREADY = ['src="/static/exams.js"', 'id="docs-nav"', 'id="metric-completed"', 'id="exam-picker"']


def main():
    if not (HERE / "main.py").exists() or not (HERE / "static").is_dir():
        print("STOP: put update_to_v6.py inside your exam_buddy folder (the one that contains main.py and the static folder).")
        sys.exit(1)
    backup = HERE / ("backup_before_v6_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
    touched = []   # (relative path, existed before)
    print("Updating Exam Buddy to version 6 ...")
    try:
        index = HERE / "static" / "index.html"
        text = index.read_text(encoding="utf-8")
        for (old, new), marker in zip(INDEX_EDITS, ALREADY):
            if marker in text:
                continue
            if old not in text:
                raise RuntimeError("static/index.html is different from what I expected (could not find: %s...). Send me this message." % old[:50])
            text = text.replace(old, new, 1)
        (backup / "static").mkdir(parents=True, exist_ok=True)
        shutil.copy2(index, backup / "static" / "index.html")
        touched.append(("static/index.html", True))
        index.write_text(text, encoding="utf-8")
        print("  edited   static/index.html")

        for rel, (digest, blob) in FILES.items():
            data = zlib.decompress(base64.b64decode(blob))
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError("this updater file is damaged (" + rel + "). Download it again.")
            target = HERE / rel
            existed = target.exists()
            if existed:
                (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup / rel)
            touched.append((rel, existed))
            target.write_bytes(data)
            print("  updated  %-22s %5.1f KB" % (rel, len(data) / 1024))
    except Exception as error:
        print("\nSOMETHING WENT WRONG: %s" % error)
        print("Putting your old files back ...")
        for rel, existed in touched:
            if existed and (backup / rel).exists():
                shutil.copy2(backup / rel, HERE / rel)
            elif not existed and (HERE / rel).exists():
                (HERE / rel).unlink()
        print("Done. Nothing was changed. Send me the message above.")
        sys.exit(1)

    print("\nYour old files are saved in: %s" % backup.name)
    print("\nALL DONE. Next steps:")
    print("  1. If the server is running it reloads by itself. If not:  python -m uvicorn main:app --reload --port 8002")
    print("  2. In the browser press Ctrl + Shift + R")
    print("  3. Student: Applications page -> pick an exam.  Overview -> new Completed box.")


if __name__ == "__main__":
    main()
